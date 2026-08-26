from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from eyened_orm import ImageInstance


def normalize(im, ce=None):
    mean = 0.485, 0.456, 0.406
    std = 0.229, 0.224, 0.225
    assert im.dtype == np.uint8

    im_norm = (im / 255.0 - mean) / std
    if ce is not None:
        ce_norm = (ce / 255.0 - mean) / std
        return np.concatenate([im_norm, ce_norm], axis=2)
    return im_norm


def as_uint8_rgb(array: np.ndarray) -> np.ndarray:
    """Convert a decoded pixel array to uint8 RGB."""
    arr = np.asarray(array)
    if arr.dtype != np.uint8:
        arr = arr.astype(np.float32)
        arr = arr - arr.min()
        mx = arr.max()
        if mx > 0:
            arr = arr / mx
        arr = (arr * 255).astype(np.uint8)
    if arr.ndim == 2:
        return np.stack([arr, arr, arr], axis=-1)
    if arr.shape[2] == 1:
        return np.repeat(arr, 3, axis=2)
    if arr.shape[2] >= 3:
        return arr[:, :, :3]
    raise ValueError(f"Unsupported image shape for fundus preprocessing: {arr.shape}")


def load_fundus_rgb(image: ImageInstance) -> np.ndarray:
    """Load a fundus image as uint8 RGB via the ORM data-access layer."""
    from eyened_orm.importer.thumbnails import pixel_array_to_2d

    arr = pixel_array_to_2d(
        image.pixel_array,
        resolution_horizontal=image.ResolutionHorizontal,
        resolution_vertical=image.ResolutionVertical,
    )
    return as_uint8_rgb(arr)


def inference_verbose() -> bool:
    return os.environ.get("EYENED_INFERENCE_VERBOSE", "0") == "1"


def ensure_nnunet_env() -> None:
    """nnU-Net v2 expects ``nnUNet_*`` env vars (not only ``NNUNET_RESULTS``)."""
    results = os.environ.get("NNUNET_RESULTS", "/nnUNet_results")
    for key in ("nnUNet_results", "nnUNet_raw", "nnUNet_preprocessed"):
        os.environ.setdefault(key, results)


def auto_device():
    import GPUtil
    import torch

    if not torch.cuda.is_available():
        return torch.device("cpu")
    try:
        device_id = GPUtil.getFirstAvailable(order="memory")[0]
        return torch.device(f"cuda:{device_id}")
    except Exception:
        # GPUtil often fails in Docker; still use the visible GPU.
        return torch.device("cuda:0")


def assert_cuda_kernel_compatible(device) -> None:
    """Fail fast when PyTorch in this environment cannot run on the visible GPU."""
    import torch

    if device.type != "cuda" or not torch.cuda.is_available():
        return
    cap = torch.cuda.get_device_capability(device)
    name = torch.cuda.get_device_name(device)
    ver = torch.__version__
    if cap[0] >= 12 and "+cu118" in ver:
        raise RuntimeError(
            f"PyTorch {ver} does not support {name} (sm_{cap[0]}{cap[1]}). "
            "Rebuild the worker image:\n"
            "  cd worker && docker compose -f docker-compose.layersegmentation.yml build"
        )
    try:
        torch.zeros(1, device=device).add_(1)
        torch.cuda.synchronize(device)
    except RuntimeError as exc:
        if "no kernel image" in str(exc).lower():
            raise RuntimeError(
                f"PyTorch {ver} cannot execute CUDA kernels on {name} (sm_{cap[0]}{cap[1]}). "
                "Rebuild the worker image:\n"
                "  cd worker && docker compose -f docker-compose.layersegmentation.yml build"
            ) from exc
        raise


def quiet_console():
    """Suppress stdout/stderr from noisy libraries unless ``EYENED_INFERENCE_VERBOSE=1``."""
    import contextlib
    import sys

    if inference_verbose():
        return contextlib.nullcontext()

    @contextlib.contextmanager
    def _suppress():
        with open(os.devnull, "w") as devnull:
            old_out, old_err = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = devnull, devnull
            try:
                yield
            finally:
                sys.stdout, sys.stderr = old_out, old_err

    return _suppress()
