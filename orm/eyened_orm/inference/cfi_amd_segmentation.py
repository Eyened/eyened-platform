"""CFI AMD segmentation: drusen, RPD, hyperpigmentation and RPE degeneration."""

import os
from os import PathLike
from typing import Dict, List, Union

import numpy as np
import torch

from eyened_orm.inference.cfi_preprocess import cfi_roi_from_input_values
from eyened_orm.inference.model_inputs import CFI_ROI_INPUT
from eyened_orm.inference.outputs import SegFeature, SegmentationOutput, SegmentationResult
from eyened_orm.inference.pipeline import Pipeline

_DESCRIPTION = "https://github.com/Eyened/cfi-amd"


def cfi_roi_projection_matrix(roi: dict | None) -> List[List[float]]:
    """Segmentation→image matrix for the 1024 crop, from stored CFI_ROI bounds.

    Same as ``ImageInstance.cropping_matrix_inverse``.
    """
    from rtnls_fundusprep.cfi_bounds import CFIBounds

    if roi is None:
        raise ValueError("No CFI_ROI bounds; cannot store native-resolution segmentation")
    return np.asarray(CFIBounds(**roi).get_cropping_transform(1024).M_inv, dtype=float).tolist()


def coerce_cfi_rgb_uint8(image: np.ndarray) -> np.ndarray:
    """Require RGB uint8 ``(H, W, 3)`` (no grayscale)."""
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError(
            f"CFI image must be RGB uint8 with shape (H, W, 3), got {arr.shape}"
        )
    if arr.dtype != np.uint8:
        raise ValueError(f"CFI image must be uint8, got {arr.dtype}")
    return np.ascontiguousarray(arr[..., :3])


class CFI_AMD(Pipeline):
    """Native mode stores the 1024 crop plus a projection matrix from CFI_ROI;
    ``upscale`` warps the maps back to the original photo."""

    output = SegmentationOutput(
        features=(
            SegFeature("drusen", "Drusen", "Drusen", "3", _DESCRIPTION),
            SegFeature("RPD", "Reticular pseudodrusen", "Reticular pseudodrusen", "3", _DESCRIPTION),
            SegFeature(
                "hyperpigmentation",
                "RPE hyperpigmentation",
                "Hyperpigmentation",
                "3",
                _DESCRIPTION,
            ),
            SegFeature(
                "rpe_degeneration",
                "Retinal pigment epithelium (RPE) degeneration",
                "RPE degeneration",
                "3",
                _DESCRIPTION,
            ),
        )
    )

    def __init__(self, device=None, *, upscale: bool = False) -> None:
        super().__init__(device, upscale=upscale)
        self.inputs = () if upscale else (CFI_ROI_INPUT,)

    def load(self) -> None:
        from cfi_amd.processor import Processor

        from eyened_orm.inference.utils import assert_cuda_kernel_compatible

        if self.device.type == "cuda":
            assert_cuda_kernel_compatible(self.device)
        self.processor = Processor(self.device, models_dir=os.environ.get("CFI_AMD_MODELS_DIR"))

    def preprocess(self, item):
        from cfi_amd.processor import preprocess_image

        matrix = None if self.upscale else cfi_roi_projection_matrix(
            cfi_roi_from_input_values(item.input_values)
        )
        return preprocess_image(item.image), matrix

    def process_batch(self, prep_batch):
        return self.processor.process_batch([prep for prep, _ in prep_batch])

    def postprocess(self, prep, maps: Dict[str, np.ndarray]) -> SegmentationResult:
        (_, T, _), matrix = prep
        if self.upscale:
            maps = {key: T.warp_inverse(value) for key, value in maps.items()}
        return SegmentationResult(maps, projection_matrix=matrix)


def predict_image(
    image: Union[np.ndarray, PathLike[str]],
    *,
    device: torch.device | None = None,
) -> Dict[str, np.ndarray]:
    """In-process CFI AMD maps in original image space (no DB). RGB uint8 array or file path."""
    from eyened_orm.inference.runner import resolve_device

    if not isinstance(image, np.ndarray):
        from cfi_amd.processor import load

        image = load(image)
    pipeline = CFI_AMD(resolve_device(CFI_AMD, device), upscale=True)
    return pipeline.predict(coerce_cfi_rgb_uint8(image)).masks
