from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Iterable, Iterator, List, Set, Tuple

import numpy as np
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
    failure_update_values,
    has_stored_value,
    image_ids_with_failed_outcome,
    image_ids_with_recorded_outcome,
    image_ids_with_succeeded_outcome,
    success_update_values,
)
from eyened_orm.inference.multi_process_inference import (
    BaseInferencePipeline,
    MultiProcessInference,
)


@dataclass(frozen=True)
class InferenceItem:
    """Picklable worker payload: decoded pixels and optional resolved input data.

    Built one image at a time by :meth:`AttributeInferencePipeline._iter_work_items`
    so the parent never retains a full-run list of pixel arrays.
    """

    image_rgb: np.ndarray | None
    input_values: dict[str, Any] | None = None


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
        self._input_values_by_image: dict[int, dict[str, AttributeValue]] = {}

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

        input_values = self._input_values_by_image.get(image_id)
        if input_values:
            av.InputValues = set(input_values.values())
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
        if not self.required_inputs:
            self._input_values_by_image = {}
            return
        self._input_values_by_image = resolve_inputs_for_images(
            self.session, set(image_ids), self.required_inputs
        )

    def _filter_images_with_required_inputs(
        self, image_ids: Iterable[int]
    ) -> Set[int]:
        if not self.required_inputs:
            return set(image_ids)

        ready: set[int] = set()
        missing = 0
        for image_id in image_ids:
            inputs = self._input_values_by_image.get(image_id, {})
            if not all(
                spec.resolved_input_name in inputs for spec in self.required_inputs
            ):
                missing += 1
                continue
            ready.add(image_id)
        if missing:
            print(f"Skipping {missing} images missing required inputs")
        return ready

    def _attribute_values_for_model_name(
        self, image_ids_set: set[int]
    ) -> list[AttributeValue]:
        from sqlalchemy import select

        stmt = (
            select(AttributeValue)
            .join(
                AttributesModel,
                AttributeValue.ModelID == AttributesModel.ModelID,
            )
            .where(
                AttributeValue.AttributeID == self.attr_definition.AttributeID,
                AttributesModel.ModelName == self.model_name,
                AttributeValue.ImageInstanceID.in_(image_ids_set),
            )
        )
        return list(self.session.scalars(stmt).all())

    def failed_image_ids_in_scope(self, image_ids: Iterable[int]) -> Set[int]:
        """Image IDs in scope that have a failed row for this model (any version)."""
        image_ids_set = set(image_ids)
        existing = self._attribute_values_for_model_name(image_ids_set)
        return image_ids_with_failed_outcome(existing) & image_ids_set

    def filter_image_ids(
        self,
        image_ids: Iterable[int],
        *,
        upgrade: bool = False,
        failed: bool = False,
        overwrite: bool = False,
    ) -> Set[int]:
        """Return image IDs that still need inference for this pipeline.

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
        from sqlalchemy import select

        image_ids_set = set(image_ids)

        if overwrite:
            pending = image_ids_set
        elif upgrade:
            stmt = select(AttributeValue).where(
                AttributeValue.AttributeID == self.attr_definition.AttributeID,
                AttributeValue.ModelID == self.model.ModelID,
                AttributeValue.ImageInstanceID.in_(image_ids_set),
            )
            existing = list(self.session.scalars(stmt).all())
            if failed:
                excluded_ids = image_ids_with_succeeded_outcome(existing)
                if excluded_ids:
                    print(
                        f"Skipping {len(excluded_ids)} images with successful results"
                    )
                pending = image_ids_set - excluded_ids
            else:
                recorded_ids = image_ids_with_recorded_outcome(existing)
                if recorded_ids:
                    print(f"Skipping {len(recorded_ids)} images with existing results")
                pending = image_ids_set - recorded_ids
        else:
            existing = self._attribute_values_for_model_name(image_ids_set)
            if failed:
                excluded_ids = image_ids_with_succeeded_outcome(existing)
                if excluded_ids:
                    print(
                        f"Skipping {len(excluded_ids)} images with successful results"
                    )
                pending = image_ids_set - excluded_ids
            else:
                recorded_ids = image_ids_with_recorded_outcome(existing)
                if recorded_ids:
                    print(f"Skipping {len(recorded_ids)} images with existing results")
                pending = image_ids_set - recorded_ids
        if self.required_inputs:
            self._ensure_inputs_resolved(pending)
            pending = self._filter_images_with_required_inputs(pending)
        else:
            self._input_values_by_image = {}

        return pending

    def _input_data_for_image(self, image_id: int) -> dict[str, Any] | None:
        """Plain input values for worker processes (ORM objects stay in the parent)."""
        if not self.required_inputs:
            return None
        inputs = self._input_values_by_image.get(image_id)
        if not inputs:
            return None
        return {
            name: attribute_value_data(av) for name, av in inputs.items()
        }

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

    def run(self, image_ids: Iterable[int], commit_interval: int = 100) -> None:
        """Run inference on a list of image IDs and save results."""
        image_ids_set = set(image_ids)
        for i, (image_id, result) in enumerate(
            tqdm(self.process(image_ids_set), total=len(image_ids_set))
        ):
            if i % commit_interval == 0:
                self.session.commit()
            if result is None:
                print(f"Image {image_id} failed to process")
                self._save_failure(image_id)
                continue
            self._save_result(image_id, result)
        self.session.commit()


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
