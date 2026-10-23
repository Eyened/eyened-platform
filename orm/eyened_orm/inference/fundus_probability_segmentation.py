"""Shared DB save / filter / run loop for 2D fundus probability masks."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence

import numpy as np

from eyened_orm import DataRepresentation, Datatype, ImageInstance, ModelSegmentation, SegmentationModel


class FundusProbabilitySegmentationPipeline:
    """Load fundus RGB, predict float masks in [0, 1], store as R8 segmentations."""

    data_representation = DataRepresentation.Probability
    datatype = Datatype.R8
    threshold = 0.5

    def __init__(
        self,
        session=None,
        device=None,
        *,
        save_only_above_threshold: bool = True,
        overwrite: bool = False,
    ) -> None:
        self.session = session
        self.device = device
        self.save_only_above_threshold = save_only_above_threshold
        self.overwrite = overwrite

    def segmentation_models(self) -> Sequence[SegmentationModel]:
        """Segmentation models produced by this pipeline (for skip-existing)."""
        return ()

    def _ensure_models_loaded(self) -> None:
        """Load external model weights; no-op unless overridden."""

    def _predict_for_image(
        self, rgb: np.ndarray
    ) -> Iterator[tuple[SegmentationModel, np.ndarray, list | None] | None]:
        """Yield ``(model, mask, projection_matrix)`` per output feature."""
        raise NotImplementedError(type(self).__name__)

    def _get_model_segmentation(
        self,
        instance_id: int,
        model: SegmentationModel,
        h: int,
        w: int,
        image_projection_matrix: list | None,
    ) -> ModelSegmentation:
        return ModelSegmentation.get_or_create(
            self.session,
            match_by={
                "ImageInstanceID": instance_id,
                "ModelID": model.ModelID,
            },
            create_kwargs={
                "Depth": 1,
                "Width": w,
                "Height": h,
                "SparseAxis": 0,
                "DataType": self.datatype,
                "DataRepresentation": self.data_representation,
                "Threshold": self.threshold,
                "ImageProjectionMatrix": image_projection_matrix,
            },
        )

    def _save_probability_mask(
        self,
        image_id: int,
        model: SegmentationModel,
        segmentation_array: np.ndarray,
        image_projection_matrix: list | None,
    ) -> None:
        existing = ModelSegmentation.by_column(
            self.session,
            ImageInstanceID=image_id,
            ModelID=model.ModelID,
        )
        if existing is not None and not self.overwrite:
            return

        h, w = segmentation_array.shape
        if existing is not None and (existing.Height, existing.Width) != (h, w):
            attr = "Height" if existing.Height != h else "Width"
            raise ValueError(f"Cannot modify {attr} of a Segmentation once created.")

        row = self._get_model_segmentation(
            image_id,
            model,
            h=h,
            w=w,
            image_projection_matrix=image_projection_matrix,
        )
        try:
            if not self.save_only_above_threshold or np.any(
                segmentation_array >= self.threshold
            ):
                if existing is not None:
                    row.ImageProjectionMatrix = image_projection_matrix
                data = (255 * segmentation_array).astype(np.uint8)
                row.write_data(data, axis=0)
        finally:
            self.session.flush()
            self.session.expunge(row)

        self.session.commit()

    def filter_image_ids(self, image_ids: Iterable[int]) -> set[int]:
        models = list(self.segmentation_models())
        if self.session is None or not models:
            return set(image_ids)

        image_ids_set = set(image_ids)
        model_ids = {model.ModelID for model in models}
        processed = set(
            ModelSegmentation.select(
                self.session,
                "ModelID",
                "ImageInstanceID",
                ImageInstanceID=image_ids_set,
                ModelID=model_ids,
            )
        )
        complete = {
            image_id
            for image_id in image_ids_set
            if all((model_id, image_id) in processed for model_id in model_ids)
        }
        if complete:
            print(f"Skipping {len(complete)} complete images")
        return image_ids_set - complete

    def run(self, image_ids: Iterable[int]) -> None:
        from eyened_orm.inference.utils import load_fundus_rgb

        self._ensure_models_loaded()
        image_ids_set = set(image_ids)
        if not image_ids_set:
            return

        for image in ImageInstance.by_ids(self.session, image_ids_set):
            rgb = load_fundus_rgb(image)
            try:
                for item in self._predict_for_image(rgb):
                    if item is None:
                        continue
                    model, mask, matrix = item
                    self._save_probability_mask(
                        image.ImageInstanceID, model, mask, matrix
                    )
            except ValueError as exc:
                self.session.rollback()
                print(
                    f"ImageInstanceID {image.ImageInstanceID}: {exc}",
                    flush=True,
                )
