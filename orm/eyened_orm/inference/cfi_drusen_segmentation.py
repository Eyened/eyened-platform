"""CFI drusen segmentation via the bundled ``cfi_drusen`` processor."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

import numpy as np

from eyened_orm import Feature, SegmentationModel
from eyened_orm.inference.fundus_probability_segmentation import (
    FundusProbabilitySegmentationPipeline,
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


class CFI_Drusen(FundusProbabilitySegmentationPipeline):
    """Drusen probabilities for color fundus photos.

    ``undo_transform=False`` stores the 1024×1024 field of view and the
    transform back to the photo. ``undo_transform=True`` stores the mask in
    the original photo (no projection matrix).
    """

    def __init__(
        self,
        session=None,
        device=None,
        *,
        save_only_above_threshold: bool = True,
        undo_transform: bool = False,
        overwrite: bool = False,
    ):
        super().__init__(
            session,
            device,
            save_only_above_threshold=save_only_above_threshold,
            overwrite=overwrite,
        )
        self.undo_transform = undo_transform
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

    def segmentation_models(self):
        return (self.model,) if self.model is not None else ()

    def _load_models(self) -> None:
        self.processor = _make_processor(self.device)

    def _ensure_models_loaded(self) -> None:
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True

    def _predict_for_image(
        self, rgb: np.ndarray
    ) -> Iterator[tuple[SegmentationModel, np.ndarray, list | None]]:
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
        yield self.model, mask, matrix


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
    from eyened_orm.inference.segmentation_runner import run_segmentation_batches

    pipeline = CFI_Drusen(
        session,
        device=device,
        undo_transform=upscale,
        overwrite=overwrite,
    )
    run_segmentation_batches(
        session,
        image_ids,
        pipeline,
        overwrite=overwrite,
        commit_after_chunk=True,
    )
