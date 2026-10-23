"""CFI drusen segmentation via the bundled ``cfi_drusen`` processor."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from eyened_orm import (
    DataRepresentation,
    Datatype,
    Feature,
    ImageInstance,
    ModelSegmentation,
    SegmentationModel,
)
FEATURE_NAME = "Drusen"
MODEL_NAME = "Drusen"
MODEL_VERSION = "4"
MODEL_DESCRIPTION = "https://github.com/Eyened/amd-features"


def _make_processor(device):
    """Load the five bundled folds onto ``device``."""
    from cfi_drusen import Processor

    if device is None:
        from eyened_orm.inference.utils import auto_device

        device = auto_device()
    return Processor(device)


def _projection_matrix(transform: dict) -> list:
    matrix = transform["M"]
    if isinstance(matrix, np.ndarray):
        return np.asarray(matrix, dtype=float).tolist()
    return matrix


class CFI_Drusen:
    """Drusen probabilities for color fundus photos.

    ``undo_transform=False`` stores the 1024×1024 field of view and the
    transform back to the photo. ``undo_transform=True`` stores the mask in
    the original photo (no projection matrix).
    """

    data_representation = DataRepresentation.Probability
    datatype = Datatype.R8
    threshold = 0.5

    def __init__(
        self,
        session=None,
        device=None,
        *,
        save_only_above_threshold: bool = True,
        undo_transform: bool = False,
        overwrite: bool = False,
    ):
        self.session = session
        self.device = device
        self.save_only_above_threshold = save_only_above_threshold
        self.undo_transform = undo_transform
        self.overwrite = overwrite
        self._models_loaded = False
        self.processor = None
        self.feature: Feature | None = None
        self.model: SegmentationModel | None = None

        if session is not None:
            self.feature = Feature.get_or_create(
                session, match_by={"FeatureName": FEATURE_NAME}
            )
            self.model = SegmentationModel.get_or_create(
                session,
                match_by={
                    "FeatureID": self.feature.FeatureID,
                    "ModelName": MODEL_NAME,
                    "Version": MODEL_VERSION,
                },
                update_values={"Description": MODEL_DESCRIPTION},
            )

    def _load_models(self) -> None:
        self.processor = _make_processor(self.device)

    def _ensure_models_loaded(self) -> None:
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True

    def _get_model_segmentation(
        self,
        instance_id: int,
        h: int,
        w: int,
        image_projection_matrix: list | None,
    ) -> ModelSegmentation:
        return ModelSegmentation.get_or_create(
            self.session,
            match_by={
                "ImageInstanceID": instance_id,
                "ModelID": self.model.ModelID,
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

    def _predict(self, rgb: np.ndarray) -> tuple[np.ndarray, list | None]:
        if self.undo_transform:
            mask = self.processor.process(rgb)
            matrix = None
        else:
            transform, mask = self.processor.process_with_transform(rgb)
            matrix = _projection_matrix(transform)
        mask = np.asarray(mask, dtype=np.float32)
        if mask.ndim == 3 and 1 in mask.shape:
            mask = np.squeeze(mask)
        if mask.ndim != 2:
            raise ValueError(f"Drusen mask must be 2D, got shape {mask.shape}")
        return mask, matrix

    def _save_result(
        self,
        image_id: int,
        segmentation_array: np.ndarray,
        image_projection_matrix: list | None,
    ) -> None:
        existing = ModelSegmentation.by_column(
            self.session,
            ImageInstanceID=image_id,
            ModelID=self.model.ModelID,
        )
        if existing is not None and not self.overwrite:
            return

        h, w = segmentation_array.shape
        if existing is not None and (existing.Height, existing.Width) != (h, w):
            attr = "Height" if existing.Height != h else "Width"
            raise ValueError(f"Cannot modify {attr} of a Segmentation once created.")

        m = self._get_model_segmentation(
            image_id,
            h=h,
            w=w,
            image_projection_matrix=image_projection_matrix,
        )
        try:
            if not self.save_only_above_threshold or np.any(
                segmentation_array >= self.threshold
            ):
                if existing is not None:
                    m.ImageProjectionMatrix = image_projection_matrix
                data = (255 * segmentation_array).astype(np.uint8)
                m.write_data(data, axis=0)
        finally:
            self.session.flush()
            self.session.expunge(m)

        self.session.commit()

    def filter_image_ids(self, image_ids: Iterable[int]) -> set[int]:
        """Drop images that already have a drusen segmentation for this model."""
        if self.session is None or self.model is None:
            return set(image_ids)
        image_ids_set = set(image_ids)
        processed = set(
            ModelSegmentation.select(
                self.session,
                "ImageInstanceID",
                ImageInstanceID=image_ids_set,
                ModelID=self.model.ModelID,
            )
        )
        if processed:
            print(f"Skipping {len(processed)} complete images")
        return image_ids_set - processed

    def run(self, image_ids: Iterable[int]) -> None:
        """Run inference and store one drusen mask per image."""
        from eyened_orm.inference.utils import load_fundus_rgb

        self._ensure_models_loaded()
        image_ids_set = set(image_ids)
        if not image_ids_set:
            return

        images = ImageInstance.by_ids(self.session, image_ids_set)
        for image in images:
            rgb = load_fundus_rgb(image)
            try:
                mask, matrix = self._predict(rgb)
                self._save_result(image.ImageInstanceID, mask, matrix)
            except ValueError as exc:
                self.session.rollback()
                print(
                    f"ImageInstanceID {image.ImageInstanceID}: {exc}",
                    flush=True,
                )


def run_for_image_ids(
    session,
    image_ids: Iterable[int],
    *,
    device=None,
    batch_size: int = 8,
    n_workers: int = 12,
    overwrite: bool = False,
    upscale: bool = False,
) -> None:
    """Entry point for the segmentation CLI.

    ``upscale=False`` stores the 1024 field of view plus the transform.
    ``upscale=True`` restores the mask to the original photo.

    ``batch_size`` and ``n_workers`` match the ``cfi-amd`` CLI. This
    processor scores one photo at a time, so both are unused.
    """
    from eyened_orm.commands.targets import iter_image_id_chunks

    image_ids = set(image_ids)
    pipeline = CFI_Drusen(
        session,
        device=device,
        undo_transform=upscale,
        overwrite=overwrite,
    )
    total_processed = 0
    chunks = list(iter_image_id_chunks(image_ids))
    for chunk_idx, chunk in enumerate(chunks, start=1):
        filtered = chunk if overwrite else pipeline.filter_image_ids(chunk)
        if not filtered:
            continue
        print(
            f"Processing {len(filtered)} images "
            f"(chunk {chunk_idx}/{len(chunks)}"
            f"{', overwrite' if overwrite else ', after filtering existing'})"
        )
        pipeline.run(filtered)
        session.commit()
        total_processed += len(filtered)

    if total_processed == 0:
        print("No images to process")
        return
    print(f"Completed processing {total_processed} images")
