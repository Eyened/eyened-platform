"""Where a model's results are stored: attribute values or segmentations.

An output is a frozen declaration on the pipeline class. ``register(session,
inputs)`` creates the database rows it needs and returns a sink bound to that
session; the runner calls ``pending``, ``save`` and ``save_failure`` on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable, Literal

import numpy as np

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributeValue,
    DataRepresentation,
    Datatype,
    Feature,
    ModelSegmentation,
    SegmentationModel,
)
from eyened_orm.inference.attribute_value_outcome import (
    attribute_value_has_stored_value_sql,
    failure_update_values,
    has_stored_value,
    success_update_values,
)
from eyened_orm.inference.model_inputs import register_model_inputs, register_model_output

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from eyened_orm.inference.model_inputs import ModelInputSpec

Mode = Literal["default", "upgrade", "failed", "overwrite"]
MODES: tuple[str, ...] = ("default", "upgrade", "failed", "overwrite")


class UnsupportedMode(ValueError):
    """The model's output cannot select images by this mode."""


def _chunks(ids: Iterable[int]):
    from eyened_orm.commands.targets import iter_image_id_chunks

    return iter_image_id_chunks(set(ids))


# --- Attribute values -------------------------------------------------------


@dataclass(frozen=True)
class AttributeOutput:
    """One ``AttributeValue`` per image for ``attribute_name``, produced by ``model_name``."""

    model_name: str
    attribute_name: str
    data_type: AttributeDataType
    version: str = "1.0"
    description: str = ""
    commit_interval: int = 100
    records_failures = True

    def register(
        self, session: Session, inputs: tuple[ModelInputSpec, ...] = ()
    ) -> AttributeSink:
        # Description is synced on every run so it follows the code.
        model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": self.model_name, "Version": self.version},
            update_values={"Description": self.description},
        )
        definition = AttributeDefinition.get_or_create(
            session,
            match_by={
                "AttributeName": self.attribute_name,
                "AttributeDataType": self.data_type,
            },
        )
        register_model_output(session, model, definition)
        register_model_inputs(session, model, inputs)
        return AttributeSink(self, session, model.ModelID, definition.AttributeID)


@dataclass
class AttributeSink:
    output: AttributeOutput
    session: Session
    model_id: int
    attribute_id: int

    def _match(self, image_id: int) -> dict[str, int]:
        return {
            "AttributeID": self.attribute_id,
            "ModelID": self.model_id,
            "ImageInstanceID": image_id,
        }

    def _ids_with_rows(
        self,
        image_ids: Iterable[int],
        *,
        current_version_only: bool = False,
        stored: bool | None = None,
    ) -> set[int]:
        """Images with a row for this attribute; ``stored`` True/False = succeeded/failed."""
        from sqlalchemy import not_, select

        stmt = select(AttributeValue.ImageInstanceID).where(
            AttributeValue.AttributeID == self.attribute_id
        )
        if current_version_only:
            stmt = stmt.where(AttributeValue.ModelID == self.model_id)
        else:
            stmt = stmt.join(
                AttributesModel, AttributeValue.ModelID == AttributesModel.ModelID
            ).where(AttributesModel.ModelName == self.output.model_name)
        if stored is True:
            stmt = stmt.where(attribute_value_has_stored_value_sql())
        elif stored is False:
            stmt = stmt.where(not_(attribute_value_has_stored_value_sql()))

        found: set[int] = set()
        for chunk in _chunks(image_ids):
            found.update(
                self.session.scalars(
                    stmt.where(AttributeValue.ImageInstanceID.in_(chunk)).distinct()
                )
            )
        return found

    def pending(self, image_ids: Iterable[int], mode: Mode) -> set[int]:
        """Images that still need inference.

        - ``default``: no row from any version of this model (succeeded or failed)
        - ``upgrade``: no row from the current version (older versions are kept)
        - ``failed``: a failed row exists and no version has succeeded
        - ``overwrite``: every image
        """
        ids = set(image_ids)
        if mode == "overwrite":
            return ids
        if mode == "failed":
            return self._ids_with_rows(ids, stored=False) - self._ids_with_rows(
                ids, stored=True
            )
        if mode == "upgrade":
            return ids - self._ids_with_rows(ids, current_version_only=True)
        return ids - self._ids_with_rows(ids)

    def save(
        self,
        image_id: int,
        result: Any,
        *,
        input_av_ids: Iterable[int] = (),
        overwrite: bool = False,
    ) -> None:
        av = AttributeValue.upsert(
            self.session,
            match_by=self._match(image_id),
            update_values=success_update_values(self.output.data_type, result),
        )
        input_av_ids = list(input_av_ids)
        if input_av_ids:
            av.InputValues = set(AttributeValue.by_ids(self.session, input_av_ids))
            self.session.add(av)

    def save_failure(self, image_id: int) -> None:
        """Record a failed attempt, unless a value is already stored for this version."""
        existing = AttributeValue.by_column(self.session, **self._match(image_id))
        if existing is not None and has_stored_value(existing):
            return
        AttributeValue.upsert(
            self.session,
            match_by=self._match(image_id),
            update_values=failure_update_values(),
        )


# --- Segmentations ----------------------------------------------------------


@dataclass(frozen=True)
class SegFeature:
    """One stored map: ``key`` names it in :class:`SegmentationResult.masks`."""

    key: str
    feature_name: str
    model_name: str
    version: str
    description: str = ""
    subfeatures: dict[int, str] | None = None


@dataclass
class SegmentationResult:
    """Masks keyed by :attr:`SegFeature.key`; 2D ``(H, W)`` or 3D ``(D, H, W)``.

    ``projection_matrix`` maps segmentation to image space (``None`` when the
    masks are already in image space).
    """

    masks: dict[str, np.ndarray]
    projection_matrix: list | None = None


@dataclass(frozen=True)
class SegmentationOutput:
    features: tuple[SegFeature, ...]
    representation: DataRepresentation = DataRepresentation.Probability
    datatype: Datatype = Datatype.R8
    threshold: float | None = 0.5
    save_only_above_threshold: bool = True
    commit_interval: int = 1
    records_failures = False

    def _feature(self, session: Session, spec: SegFeature) -> Feature:
        if spec.subfeatures is None:
            return Feature.get_or_create(session, match_by={"FeatureName": spec.feature_name})
        feature = Feature.by_name(session, spec.feature_name)
        if feature is None:
            return Feature.from_list(session, spec.feature_name, spec.subfeatures)
        if feature.subfeatures != spec.subfeatures:
            raise ValueError(
                f"Feature subfeatures do not match: "
                f"{feature.subfeatures} != {spec.subfeatures}"
            )
        return feature

    def register(
        self, session: Session, inputs: tuple[ModelInputSpec, ...] = ()
    ) -> SegmentationSink:
        model_ids: dict[str, int] = {}
        for spec in self.features:
            feature = self._feature(session, spec)
            model = SegmentationModel.get_or_create(
                session,
                match_by={
                    "FeatureID": feature.FeatureID,
                    "ModelName": spec.model_name,
                    "Version": spec.version,
                },
                update_values={"Description": spec.description},
            )
            model_ids[spec.key] = model.ModelID
        return SegmentationSink(self, session, model_ids)


@dataclass
class SegmentationSink:
    output: SegmentationOutput
    session: Session
    model_ids: dict[str, int] = field(default_factory=dict)

    def pending(self, image_ids: Iterable[int], mode: Mode) -> set[int]:
        """Images missing a map for any feature of the current version."""
        if mode == "failed":
            raise UnsupportedMode(
                "Segmentation models do not record failures; use default or overwrite"
            )
        ids = set(image_ids)
        if mode == "overwrite":
            return ids
        wanted = set(self.model_ids.values())
        done: set[tuple[int, int]] = set()
        for chunk in _chunks(ids):
            done.update(
                ModelSegmentation.select(
                    self.session,
                    "ModelID",
                    "ImageInstanceID",
                    ImageInstanceID=set(chunk),
                    ModelID=wanted,
                )
            )
        return {i for i in ids if not all((m, i) in done for m in wanted)}

    def _encode(self, mask: np.ndarray) -> np.ndarray:
        if self.output.representation == DataRepresentation.Probability:
            return (255 * mask).astype(np.uint8)
        return mask.astype(np.uint8)

    def _save_mask(
        self,
        image_id: int,
        model_id: int,
        mask: np.ndarray,
        matrix: list | None,
        overwrite: bool,
    ) -> None:
        existing = ModelSegmentation.by_column(
            self.session, ImageInstanceID=image_id, ModelID=model_id
        )
        if existing is not None and not overwrite:
            return
        depth, height, width = (1, *mask.shape) if mask.ndim == 2 else mask.shape
        if existing is not None:
            for attr, value in (("Depth", depth), ("Height", height), ("Width", width)):
                if getattr(existing, attr) != value:
                    raise ValueError(f"Cannot modify {attr} of a Segmentation once created.")

        row = ModelSegmentation.get_or_create(
            self.session,
            match_by={"ImageInstanceID": image_id, "ModelID": model_id},
            create_kwargs={
                "Depth": depth,
                "Height": height,
                "Width": width,
                "SparseAxis": 0,
                "ScanIndices": list(range(depth)) if mask.ndim == 3 else None,
                "DataType": self.output.datatype,
                "DataRepresentation": self.output.representation,
                "Threshold": self.output.threshold,
                "ImageProjectionMatrix": matrix,
            },
        )
        try:
            threshold = self.output.threshold
            if (
                not self.output.save_only_above_threshold
                or threshold is None
                or np.any(mask >= threshold)
            ):
                # create_kwargs does not touch an existing row; the matrix
                # follows this run (native crop vs image space).
                row.ImageProjectionMatrix = matrix
                data = self._encode(mask)
                if mask.ndim == 2:
                    row.write_data(data, axis=0)
                else:
                    row.write_data(data)
        finally:
            # Keep the identity map from growing over long runs.
            self.session.flush()
            self.session.expunge(row)

    def save(
        self,
        image_id: int,
        result: SegmentationResult,
        *,
        input_av_ids: Iterable[int] = (),
        overwrite: bool = False,
    ) -> None:
        for key, mask in result.masks.items():
            if key not in self.model_ids:
                continue
            self._save_mask(
                image_id,
                self.model_ids[key],
                np.asarray(mask),
                result.projection_matrix,
                overwrite,
            )

    def save_failure(self, image_id: int) -> None:
        """Segmentations keep no failure rows; the runner reports failures instead."""
