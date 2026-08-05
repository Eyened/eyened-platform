from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, ClassVar, Iterable, Iterator, List, Set, Tuple

import numpy as np
from sqlalchemy.exc import OperationalError
from tqdm import tqdm

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributeValue,
    ImageInstance,
    Modality,
)
from eyened_orm.inference.model_inputs import (
    ModelInputSpec,
    attribute_value_data,
    register_model_inputs,
    register_model_output,
    resolve_inputs_for_images,
)
from eyened_orm.inference.attribute_value_outcome import (
    attribute_value_has_stored_value_sql,
    failure_update_values,
    has_stored_value,
    success_update_values,
)
from eyened_orm.inference.multi_process_inference import (
    BaseInferencePipeline,
    MultiProcessInference,
)

# MySQL: 1205 lock wait timeout, 1213 deadlock
_RETRYABLE_MYSQL_ERRNOS = frozenset({1205, 1213})


def _is_retryable_db_error(exc: BaseException) -> bool:
    if not isinstance(exc, OperationalError):
        return False
    orig = getattr(exc, "orig", None)
    errno = getattr(orig, "args", (None,))[0] if orig is not None else None
    return errno in _RETRYABLE_MYSQL_ERRNOS


@dataclass(frozen=True)
class InferenceItem:
    """Picklable worker payload: decoded pixels and optional resolved input data.

    Built one image at a time by :meth:`AttributeInferencePipeline._iter_work_items`
    so the parent never retains a full-run list of pixel arrays.
    """

    image_rgb: np.ndarray | None
    input_values: dict[str, Any] | None = None


@dataclass(frozen=True)
class FilterStats:
    """Outcome of :meth:`AttributeInferencePipeline.filter_image_ids` for one call."""

    considered: int
    pending: int
    skipped_existing: int = 0
    skipped_successful: int = 0
    skipped_missing_inputs: int = 0

    @property
    def skipped_total(self) -> int:
        return (
            self.skipped_existing
            + self.skipped_successful
            + self.skipped_missing_inputs
        )


class AttributeInferencePipeline(BaseInferencePipeline):
    """Base class for inference pipelines that produce attribute values.

    Subclasses should define:
    - model_name: str - name of the AttributesModel
    - model_version: str - version of the AttributesModel; set ``self.model_version``
      before ``super().__init__`` when derived from an installed package or HF artifact
    - model_description: Optional[str] - description for model creation
    - attribute_name: str - name of the AttributeDefinition
    - attribute_data_type: AttributeDataType - data type (JSON, Float, etc.)
    - required_inputs: tuple of ModelInputSpec for input dependencies

    Subclasses can override:
    - _load_models() - called before processing starts
    - filter_image_ids(image_ids) - filter/skip existing (return filtered set)
    - _save_result(image_id, result) - customize how results are saved

    PyTorch-based pipelines should subclass :class:`TorchAttributeInferencePipeline`
    instead (so environments without torch can import this module).
    """

    # Subclasses should define these class attributes
    model_name: str
    model_version: str = "1.0"
    model_description: str = ""
    attribute_name: str
    attribute_data_type: AttributeDataType
    supported_modalities: ClassVar[tuple[Modality, ...]] = ()
    required_inputs: ClassVar[tuple[ModelInputSpec, ...]] = ()

    def __init__(
        self,
        session,
        n_workers: int = 8,
        **kwargs,
    ):
        """Initialize the inference pipeline.

        Args:
            session: Database session
            n_workers: Number of preprocessing worker processes
            **kwargs: Additional arguments stored as instance attributes
        """
        self.session = session
        self.n_workers = n_workers
        # Plain snapshots only — never hand live ORM AttributeValues to the MPI
        # feeder thread (sessions are not thread-safe; commits expire objects).
        self._input_data_by_image: dict[int, dict[str, Any]] = {}
        self._input_av_ids_by_image: dict[int, dict[str, int]] = {}
        self.last_filter_stats: FilterStats | None = None

        # Store any additional kwargs as instance attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Create or retrieve AttributesModel; sync Description on each run (see layer_segmentation / cfi_amd).
        self.model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": self.model_name, "Version": self.model_version},
            update_values={"Description": self.model_description},
        )

        # Create or retrieve AttributeDefinition
        self.attr_definition = AttributeDefinition.get_or_create(
            session,
            match_by={
                "AttributeName": self.attribute_name,
                "AttributeDataType": self.attribute_data_type,
            },
        )

        self._register_model_io()

        # Track if models have been loaded
        self._models_loaded = False

    def _register_model_io(self) -> None:
        """Register declared model outputs and inputs in the database."""
        register_model_output(self.session, self.model, self.attr_definition)
        register_model_inputs(self.session, self.model, self.required_inputs)

    def _load_models(self) -> None:
        """Load models before processing. Override in subclasses that need model loading."""
        pass

    def _ensure_models_loaded(self) -> None:
        """Ensure models are loaded (only loads once)."""
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True

    def _save_result(self, image_id: int, result: Any) -> None:
        """Save result to database and link input provenance when available."""
        av = AttributeValue.upsert(
            self.session,
            match_by={
                "AttributeID": self.attr_definition.AttributeID,
                "ModelID": self.model.ModelID,
                "ImageInstanceID": image_id,
            },
            update_values=success_update_values(self.attribute_data_type, result),
        )

        input_ids = self._input_av_ids_by_image.get(image_id)
        if input_ids:
            # Re-load by PK in this write session (IDs snapshotted before MPI).
            linked = AttributeValue.by_ids(self.session, input_ids.values())
            av.InputValues = set(linked)
            self.session.add(av)

    def _save_failure(self, image_id: int) -> None:
        """Record a failed inference attempt (null value columns, row retained).

        Skips the write when a row already holds a value so a retry or batch
        failure cannot erase a previously successful result.
        """
        match_by = {
            "AttributeID": self.attr_definition.AttributeID,
            "ModelID": self.model.ModelID,
            "ImageInstanceID": image_id,
        }
        existing = AttributeValue.by_column(self.session, **match_by)
        if existing is not None and has_stored_value(existing):
            return
        AttributeValue.upsert(
            self.session,
            match_by=match_by,
            update_values=failure_update_values(),
        )

    def _ensure_inputs_resolved(self, image_ids: Iterable[int]) -> None:
        """Resolve required inputs and snapshot plain data + AttributeValue IDs.

        Live ORM objects are not retained: the MPI feeder thread must only see
        picklable plain values, and mid-run commits must not expire objects the
        feeder still holds.
        """
        if not self.required_inputs:
            self._input_data_by_image = {}
            self._input_av_ids_by_image = {}
            return
        resolved = resolve_inputs_for_images(
            self.session, set(image_ids), self.required_inputs
        )
        data_by_image: dict[int, dict[str, Any]] = {}
        ids_by_image: dict[int, dict[str, int]] = {}
        for image_id, inputs in resolved.items():
            data_by_image[image_id] = {
                name: attribute_value_data(av) for name, av in inputs.items()
            }
            ids_by_image[image_id] = {
                name: av.AttributeValueID for name, av in inputs.items()
            }
        self._input_data_by_image = data_by_image
        self._input_av_ids_by_image = ids_by_image

    def _filter_images_with_required_inputs(
        self, image_ids: Iterable[int]
    ) -> tuple[Set[int], int]:
        """Return ``(ready_ids, missing_count)`` for required model inputs."""
        if not self.required_inputs:
            return set(image_ids), 0

        ready: set[int] = set()
        missing = 0
        for image_id in image_ids:
            inputs = self._input_data_by_image.get(image_id, {})
            if not all(
                spec.resolved_input_name in inputs for spec in self.required_inputs
            ):
                missing += 1
                continue
            ready.add(image_id)
        return ready, missing

    def _attribute_value_image_id_stmt(self, *, model_id: int | None = None):
        """Select ``ImageInstanceID`` for this attribute + model (name or ID)."""
        from sqlalchemy import select

        stmt = select(AttributeValue.ImageInstanceID).where(
            AttributeValue.AttributeID == self.attr_definition.AttributeID,
        )
        if model_id is not None:
            return stmt.where(AttributeValue.ModelID == model_id)
        return stmt.join(
            AttributesModel,
            AttributeValue.ModelID == AttributesModel.ModelID,
        ).where(AttributesModel.ModelName == self.model_name)

    def _image_ids_with_any_row(self, *, model_id: int | None = None) -> Set[int]:
        """Image IDs that have any AttributeValue row (ID-only; no value payloads)."""
        stmt = self._attribute_value_image_id_stmt(model_id=model_id).distinct()
        return set(self.session.scalars(stmt).all())

    def _image_ids_with_succeeded_row(self, *, model_id: int | None = None) -> Set[int]:
        """Image IDs with a non-null value column for this attribute/model."""
        has_value = attribute_value_has_stored_value_sql()
        stmt = (
            self._attribute_value_image_id_stmt(model_id=model_id)
            .where(has_value)
            .distinct()
        )
        return set(self.session.scalars(stmt).all())

    def _image_ids_with_failed_row(self, *, model_id: int | None = None) -> Set[int]:
        """Image IDs with an all-null value row for this attribute/model."""
        from sqlalchemy import not_

        has_value = attribute_value_has_stored_value_sql()
        stmt = (
            self._attribute_value_image_id_stmt(model_id=model_id)
            .where(not_(has_value))
            .distinct()
        )
        return set(self.session.scalars(stmt).all())

    def failed_image_ids_in_scope(self, image_ids: Iterable[int]) -> Set[int]:
        """Image IDs in scope that have a failed row for this model (any version)."""
        return self._image_ids_with_failed_row() & set(image_ids)

    def select_pending_by_outcomes(
        self,
        image_ids: Iterable[int],
        *,
        upgrade: bool = False,
        failed: bool = False,
        overwrite: bool = False,
    ) -> Set[int]:
        """Return IDs that still need inference based on existing AttributeValue rows.

        One or two ID-only SQL queries cover the whole attribute/model space;
        results are intersected with ``image_ids`` in Python. Does **not** apply
        required-input filtering — follow up with :meth:`filter_image_ids`
        (typically per chunk, ``overwrite=True``) when inputs are required.

        Sets :attr:`last_filter_stats` (``skipped_missing_inputs`` is always 0).
        """
        image_ids_set = set(image_ids)
        skipped_existing = 0
        skipped_successful = 0

        if overwrite:
            pending = image_ids_set
        elif failed:
            if upgrade:
                succeeded_ids = self._image_ids_with_succeeded_row(
                    model_id=self.model.ModelID
                )
            else:
                succeeded_ids = self._image_ids_with_succeeded_row()
            excluded = succeeded_ids & image_ids_set
            skipped_successful = len(excluded)
            pending = image_ids_set - succeeded_ids
        elif upgrade:
            recorded_ids = self._image_ids_with_any_row(model_id=self.model.ModelID)
            excluded = recorded_ids & image_ids_set
            skipped_existing = len(excluded)
            pending = image_ids_set - recorded_ids
        else:
            recorded_ids = self._image_ids_with_any_row()
            excluded = recorded_ids & image_ids_set
            skipped_existing = len(excluded)
            pending = image_ids_set - recorded_ids

        self.last_filter_stats = FilterStats(
            considered=len(image_ids_set),
            pending=len(pending),
            skipped_existing=skipped_existing,
            skipped_successful=skipped_successful,
            skipped_missing_inputs=0,
        )
        return pending

    def filter_image_ids(
        self,
        image_ids: Iterable[int],
        *,
        upgrade: bool = False,
        failed: bool = False,
        overwrite: bool = False,
    ) -> Set[int]:
        """Return image IDs that still need inference for this pipeline.

        Sets :attr:`last_filter_stats` with per-call skip counts (caller should
        print progress; this method does not print).

        **Default** (``upgrade=False``, ``failed=False``, ``overwrite=False``):
        exclude images that already have any ``AttributeValue`` row for this
        attribute from any version of ``model_name`` (succeeded or failed).

        **Upgrade** (``upgrade=True``): exclude only images that already have a
        row for the **current** pipeline version (``self.model.ModelID``).
        Images with older versions only are included so a new version can be
        written alongside existing output without overwriting it.

        **Failed** (``failed=True``): exclude only images that already have a
        **succeeded** row for this model (any version). Failed rows are
        retried. Combine with a prior call to :meth:`failed_image_ids_in_scope`
        to limit the target set to failed images only.

        **Overwrite** (``overwrite=True``): do not skip images based on existing
        output; still skip images missing required inputs.
        """
        pending = self.select_pending_by_outcomes(
            image_ids, upgrade=upgrade, failed=failed, overwrite=overwrite
        )
        outcome_stats = self.last_filter_stats
        assert outcome_stats is not None

        if self.required_inputs:
            self._ensure_inputs_resolved(pending)
            pending, skipped_missing_inputs = self._filter_images_with_required_inputs(
                pending
            )
        else:
            self._input_data_by_image = {}
            self._input_av_ids_by_image = {}
            skipped_missing_inputs = 0

        self.last_filter_stats = FilterStats(
            considered=outcome_stats.considered,
            pending=len(pending),
            skipped_existing=outcome_stats.skipped_existing,
            skipped_successful=outcome_stats.skipped_successful,
            skipped_missing_inputs=skipped_missing_inputs,
        )
        return pending

    def _input_data_for_image(self, image_id: int) -> dict[str, Any] | None:
        """Return snapshotted plain input values for the MPI feeder / workers."""
        if not self.required_inputs:
            return None
        inputs = self._input_data_by_image.get(image_id)
        return inputs or None

    def _load_image_rgb(self, image: ImageInstance) -> np.ndarray:
        """Load decoded pixels for one image. Override in modality-specific subclasses."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement _load_image_rgb"
        )

    def _load_inference_item(
        self, load_session, image_id: int
    ) -> InferenceItem | None:
        """Load one image into an ``InferenceItem`` using ``load_session``.

        The ORM instance is expunged after decode so the session identity map
        does not retain images (or their pixel buffers) across the run.
        """
        try:
            image = load_session.get(ImageInstance, image_id)
            if image is None:
                print(f"Image {image_id} not found")
                return None
            item = InferenceItem(
                image_rgb=self._load_image_rgb(image),
                input_values=self._input_data_for_image(image_id),
            )
            load_session.expunge(image)
            return item
        except Exception as exc:
            print(f"Failed to load image {image_id}: {exc}")
            try:
                load_session.rollback()
            except Exception:
                pass
            return None

    def _iter_work_items(
        self, image_ids: Iterable[int]
    ) -> Iterator[tuple[int, InferenceItem | None]]:
        """Yield ``(image_id, item)`` one at a time without a bulk ``by_ids``.

        Uses a dedicated session so this can run in the MPI feeder thread
        without sharing the parent write session. Decoded arrays live only
        until ``MultiProcessInference``'s bounded work queue accepts them.
        """
        from sqlalchemy.orm import sessionmaker

        SessionLocal = sessionmaker(bind=self.session.get_bind())
        with SessionLocal() as load_session:
            for image_id in image_ids:
                yield image_id, self._load_inference_item(load_session, image_id)

    def process(self, image_ids: Iterable[int]) -> Iterator[Tuple[int, Any]]:
        """Process images and yield (image_id, result) tuples."""
        self._ensure_models_loaded()

        image_ids_list = list(dict.fromkeys(image_ids))
        if not image_ids_list:
            return

        self._ensure_inputs_resolved(image_ids_list)

        mpi = MultiProcessInference(
            self._iter_work_items(image_ids_list),
            pipeline=self,
            n_workers=self.n_workers,
            batch_size=getattr(self, "batch_size", 1),
        )
        yield from mpi.run()

    def _apply_pending_outcome(self, image_id: int, result: Any | None) -> None:
        """Stage one outcome in the current session (no commit)."""
        if result is None:
            self._save_failure(image_id)
        else:
            self._save_result(image_id, result)

    def _commit_pending_batch(
        self,
        pending: list[tuple[int, Any | None]],
        *,
        max_attempts: int = 3,
    ) -> None:
        """Apply ``pending`` outcomes and commit; replay the whole batch on lock/deadlock.

        ``pending`` holds plain ``(image_id, result)`` pairs (``result is None`` means
        failure). On MySQL 1205/1213 we rollback and re-apply every item before
        retrying commit, so uncommitted siblings are never silently dropped.
        """
        if not pending:
            return
        for attempt in range(1, max_attempts + 1):
            try:
                for image_id, result in pending:
                    self._apply_pending_outcome(image_id, result)
                self.session.commit()
                pending.clear()
                return
            except OperationalError as exc:
                if not _is_retryable_db_error(exc) or attempt >= max_attempts:
                    raise
                print(
                    f"commit batch ({len(pending)} images): {exc.orig}; "
                    f"rollback and retry {attempt}/{max_attempts}"
                )
                self.session.rollback()
                time.sleep(0.5 * (2 ** (attempt - 1)))
        raise AssertionError("unreachable")  # pragma: no cover

    def run(self, image_ids: Iterable[int], commit_interval: int = 100) -> None:
        """Run inference on a list of image IDs and save results."""
        image_ids_set = set(image_ids)
        pending: list[tuple[int, Any | None]] = []
        for image_id, result in tqdm(
            self.process(image_ids_set), total=len(image_ids_set)
        ):
            if result is None:
                print(f"Image {image_id} failed to process")
            pending.append((image_id, result))
            if len(pending) >= commit_interval:
                self._commit_pending_batch(pending)
        self._commit_pending_batch(pending)


class CFIAttributeInferencePipeline(AttributeInferencePipeline):
    """Color fundus attribute pipelines: load pixels via the ORM data-access layer."""

    def _load_image_rgb(self, image: ImageInstance) -> np.ndarray:
        from eyened_orm.inference.utils import load_fundus_rgb

        return load_fundus_rgb(image)


class TorchAttributeInferencePipeline(CFIAttributeInferencePipeline):
    """Attribute pipeline that runs PyTorch models (imports ``torch`` only when used)."""

    def _prepare_torch_batch(self, prep_batch: List[Any]) -> Any:
        """Prepare preprocessed batch for torch processing."""
        import torch

        x_np = np.stack([x_im.transpose(2, 0, 1) for _, x_im in prep_batch], axis=0)
        return torch.from_numpy(x_np).to(device=self.device, dtype=torch.float32)

    def _run_torch_forward(self, x_in: Any, model_forward_fn) -> np.ndarray:
        import torch

        with torch.no_grad():
            return model_forward_fn(x_in).detach().cpu().numpy()
