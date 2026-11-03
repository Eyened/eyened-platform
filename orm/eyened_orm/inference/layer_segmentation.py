"""OCT retinal layer segmentation via nnU-Net v2 (Eyened/LayerSegmentation on Hugging Face)."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import warnings
from os import PathLike
from pathlib import Path
from typing import Union

import numpy as np
import torch
from PIL import Image

from eyened_orm import DataRepresentation, Datatype
from eyened_orm.inference.outputs import SegFeature, SegmentationOutput, SegmentationResult
from eyened_orm.inference.pipeline import Pipeline
from eyened_orm.inference.utils import (
    assert_cuda_kernel_compatible,
    ensure_nnunet_env,
    inference_verbose,
    quiet_console,
)

LAYER_SUBFEATURES = {
    0: "background",
    1: "Retinal Nerve Fiber Layer (RNFL)",
    2: "Ganglion cell layer (GCL)",
    3: "Inner plexiform layer (IPL)",
    4: "Inner nuclear layer (INL)",
    5: "Outer plexiform layer (OPL)",
    6: "Outer nuclear layer (ONL)",
    7: "External limiting membrane (ELM)",
    8: "Myoid zone (MZ)",
    9: "Ellipsoid zone (EZ)",
    10: "Outer Segments (OS)",
    11: "Inter Digitation Zone (IDZ)",
    12: "Retinal pigment epithelium (RPE)",
    13: "Choroid",
    14: "Other",
}
LAYER_FEATURES = [LAYER_SUBFEATURES[i] for i in range(1, len(LAYER_SUBFEATURES))]

DEFAULT_MODEL_DIR = (
    Path(os.environ.get("NNUNET_RESULTS", "/nnUNet_results"))
    / "Dataset506_layers_v2_correctedset"
    / "nnUNetTrainer__nnUNetPlans__2d"
)
NNUNET_FOLDS: tuple[int, ...] = (0, 1, 2, 3, 4)
LayerVolumeInput = Union[np.ndarray, PathLike[str]]


def _log(msg: str) -> None:
    print(f"[layer-segmentation] {msg}", flush=True)


def _model_dir() -> Path:
    path = Path(os.environ.get("LAYER_SEGMENTATION_MODEL_DIR", DEFAULT_MODEL_DIR))
    if not path.is_dir():
        raise FileNotFoundError(f"Layer segmentation model not found at {path}")
    return path


def load_layer_volume(volume: LayerVolumeInput) -> np.ndarray:
    """Load an OCT volume from a ``.npy`` path or validate a ``(D, H, W)`` uint8 array."""
    if isinstance(volume, (str, os.PathLike)):
        volume = np.load(volume)
    if not isinstance(volume, np.ndarray):
        raise TypeError(f"Expected ndarray or path, got {type(volume).__name__}")
    if volume.dtype != np.uint8:
        raise ValueError(f"OCT volume must be uint8, got {volume.dtype}")
    if volume.ndim not in (2, 3):
        raise ValueError(f"Expected 2D or 3D OCT volume, got shape {volume.shape}")
    return volume


def masks_to_array(output_dir: Path, shape: tuple[int, int, int]) -> np.ndarray:
    """Stack per-scan nnU-Net PNGs into ``(D, H, W)`` uint8 class maps."""
    layers = np.zeros(shape, dtype=np.uint8)
    for i in range(shape[0]):
        path = output_dir / f"scan_{i:05d}.png"
        if not path.exists():
            raise FileNotFoundError(f"Missing nnUNet output: {path}")
        mask = np.asarray(Image.open(path))
        layers[i] = (mask[..., 0] if mask.ndim == 3 else mask).astype(np.uint8)
    return layers


class LayerSegmentation(Pipeline):
    """nnU-Net layer segmentation for OCT volumes (one volume per batch, in-process)."""

    output = SegmentationOutput(
        features=(
            SegFeature(
                "layers",
                "Macular Layers NEW",
                "nnUNet macular layers v3",
                "3",
                "2D UNet for macular layers, finetuned on pixelwise corrected data "
                "(https://huggingface.co/Eyened/LayerSegmentation)",
                subfeatures=LAYER_SUBFEATURES,
            ),
        ),
        representation=DataRepresentation.MultiClass,
        datatype=Datatype.R8UI,
        threshold=None,
    )
    image_input = "volume"

    def load(self) -> None:
        from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

        ensure_nnunet_env()
        use_cuda = self.device.type == "cuda"
        if use_cuda:
            assert_cuda_kernel_compatible(self.device)
        else:
            _log("WARNING: running on CPU — use Docker with --gpus all")
        verbose = inference_verbose()
        self.predictor = nnUNetPredictor(
            perform_everything_on_device=use_cuda,
            device=self.device,
            verbose=verbose,
            verbose_preprocessing=verbose,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.predictor.initialize_from_trained_model_folder(
                str(_model_dir()),
                use_folds=NNUNET_FOLDS,
                checkpoint_name="checkpoint_final.pth",
            )

    def preprocess(self, item) -> np.ndarray:
        volume = np.asarray(item.image)
        return volume[None] if volume.ndim == 2 else volume

    def _segment(self, volume: np.ndarray) -> np.ndarray:
        """nnU-Net works on files: write B-scans as PNGs, predict, read masks back."""
        work_dir = Path(tempfile.mkdtemp(prefix="layerseg_"))
        try:
            input_dir, output_dir = work_dir / "nnunet_in", work_dir / "nnunet_out"
            input_dir.mkdir()
            output_dir.mkdir()
            for i, scan in enumerate(volume):
                Image.fromarray(scan).save(input_dir / f"scan_{i:05d}_0000.png")
            t0 = time.perf_counter()
            n_proc = 2 if inference_verbose() else 1
            with quiet_console():
                self.predictor.predict_from_files(
                    str(input_dir),
                    str(output_dir),
                    save_probabilities=False,
                    overwrite=True,
                    num_processes_preprocessing=n_proc,
                    num_processes_segmentation_export=n_proc,
                )
            _log(f"{volume.shape[0]} B-scans in {time.perf_counter() - t0:.1f}s")
            return masks_to_array(output_dir, volume.shape)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def process_batch(self, volumes):
        return [self._segment(volume) for volume in volumes]

    def postprocess(self, volume, layers: np.ndarray) -> SegmentationResult:
        return SegmentationResult({"layers": layers})


def predict_volume(
    volume: LayerVolumeInput,
    *,
    device: torch.device | None = None,
) -> np.ndarray:
    """In-process layer prediction (no DB). ``volume`` is uint8 ``(D, H, W)`` or a ``.npy`` path."""
    from eyened_orm.inference.runner import resolve_device

    pipeline = LayerSegmentation(resolve_device(LayerSegmentation, device))
    return pipeline.predict(load_layer_volume(volume)).masks["layers"]
