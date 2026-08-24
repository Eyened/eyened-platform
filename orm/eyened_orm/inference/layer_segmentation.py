"""OCT retinal layer segmentation via nnU-Net v2 (Eyened/LayerSegmentation on Hugging Face)."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from os import PathLike
from typing import Iterable, Set, Union

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

from eyened_orm import (
    DataRepresentation,
    Datatype,
    Feature,
    ImageInstance,
    ModelSegmentation,
    SegmentationModel,
)
from eyened_orm.inference.utils import (
    assert_cuda_kernel_compatible,
    auto_device,
    ensure_nnunet_env,
    inference_verbose,
    quiet_console,
)

MODEL_DESCRIPTION = (
    "2D UNet for macular layers, finetuned on pixelwise corrected data "
    "(https://huggingface.co/Eyened/LayerSegmentation)"
)
FEATURE_NAME = "Macular Layers NEW"
MODEL_NAME = "nnUNet macular layers v3"
MODEL_VERSION = "3"

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


def _log(msg: str, *, minimal: bool = False) -> None:
    if minimal or inference_verbose():
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


@dataclass
class LayerPreppedVolume:
    """Preprocessed OCT volume on disk for nnU-Net (under a temp work directory)."""

    image_instance_id: int
    depth: int
    height: int
    width: int
    work_dir: Path

    @property
    def input_dir(self) -> Path:
        return self.work_dir / "nnunet_in"

    @property
    def output_dir(self) -> Path:
        return self.work_dir / "nnunet_out"

    def cleanup(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)


class LayerSegmentation:
    """nnU-Net layer segmentation for OCT volumes."""

    data_representation = DataRepresentation.MultiClass
    datatype = Datatype.R8UI

    def __init__(self, session=None, device: torch.device | None = None):
        self.session = session
        self.device = device if device is not None else auto_device()
        self._predictor = None
        self.feature = None
        self.model = None

        if session is not None:
            self.feature = Feature.by_name(session, FEATURE_NAME)
            if self.feature is None:
                self.feature = Feature.from_list(
                    session, FEATURE_NAME, LAYER_SUBFEATURES
                )
            elif self.feature.subfeatures != LAYER_SUBFEATURES:
                raise ValueError(
                    f"Feature subfeatures do not match: "
                    f"{self.feature.subfeatures} != {LAYER_SUBFEATURES}"
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

    def _ensure_predictor(self) -> None:
        if self._predictor is not None:
            return

        from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

        ensure_nnunet_env()
        use_cuda = self.device.type == "cuda"
        verbose = inference_verbose()
        if verbose:
            _log(f"Loading nnU-Net from {_model_dir()} | device={self.device}")
            if use_cuda:
                assert_cuda_kernel_compatible(self.device)
            else:
                _log("WARNING: running on CPU — use Docker with --gpus all")

        t0 = time.perf_counter()
        self._predictor = nnUNetPredictor(
            perform_everything_on_device=use_cuda,
            device=self.device,
            verbose=verbose,
            verbose_preprocessing=verbose,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self._predictor.initialize_from_trained_model_folder(
                str(_model_dir()),
                use_folds=NNUNET_FOLDS,
                checkpoint_name="checkpoint_final.pth",
            )
        if verbose:
            _log(f"nnU-Net ready in {time.perf_counter() - t0:.1f}s")

    def _prep_volume(
        self, volume: np.ndarray, *, image_instance_id: int = 0
    ) -> LayerPreppedVolume:
        t0 = time.perf_counter()
        if volume.ndim == 2:
            slices = [volume]
        elif volume.ndim == 3:
            slices = list(volume)
        else:
            raise ValueError(f"Expected 2D or 3D array, got shape {volume.shape}")

        depth = len(slices)
        height, width = slices[0].shape
        _log(f"preprocessing ({depth}, {height}, {width})", minimal=True)

        work_dir = Path(tempfile.mkdtemp(prefix="layerseg_"))
        input_dir, output_dir = work_dir / "nnunet_in", work_dir / "nnunet_out"
        input_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)
        t_png = time.perf_counter()
        for i, slc in enumerate(slices):
            Image.fromarray(slc).save(input_dir / f"scan_{i:05d}_0000.png")
        _log(
            f"prep: wrote {depth} input PNGs in {time.perf_counter() - t_png:.1f}s "
            f"(total prep {time.perf_counter() - t0:.1f}s)",
            minimal=True,
        )

        return LayerPreppedVolume(
            image_instance_id=image_instance_id,
            depth=depth,
            height=height,
            width=width,
            work_dir=work_dir,
        )

    def _run_nnunet(self, prep: LayerPreppedVolume) -> None:
        n_proc = 2 if inference_verbose() else 1
        _log(f"nnU-Net: {prep.depth} B-scans", minimal=True)
        t0 = time.perf_counter()
        with quiet_console():
            self._predictor.predict_from_files(
                str(prep.input_dir),
                str(prep.output_dir),
                save_probabilities=False,
                overwrite=True,
                num_processes_preprocessing=n_proc,
                num_processes_segmentation_export=n_proc,
            )
        _log(f"nnU-Net done in {time.perf_counter() - t0:.1f}s", minimal=True)

    @staticmethod
    def masks_to_array(prep: LayerPreppedVolume) -> np.ndarray:
        """Stack per-scan nnU-Net PNGs into ``(D, H, W)`` uint8 class maps."""
        t0 = time.perf_counter()
        layers = np.zeros((prep.depth, prep.height, prep.width), dtype=np.uint8)
        for i in range(prep.depth):
            path = prep.output_dir / f"scan_{i:05d}.png"
            if not path.exists():
                raise FileNotFoundError(f"Missing nnUNet output: {path}")
            mask = np.asarray(Image.open(path))
            if mask.ndim == 3:
                mask = mask[..., 0]
            layers[i] = mask.astype(np.uint8)
        _log(
            f"stacked {prep.depth} mask PNGs -> {layers.shape} "
            f"in {time.perf_counter() - t0:.1f}s",
            minimal=True,
        )
        return layers

    def predict_volume(self, volume: np.ndarray) -> np.ndarray:
        """Run preprocess → nnU-Net → stack masks (no database)."""
        t0 = time.perf_counter()
        prep = self._prep_volume(volume)
        try:
            self._ensure_predictor()
            self._run_nnunet(prep)
            layers = self.masks_to_array(prep)
            _log(f"done {layers.shape} in {time.perf_counter() - t0:.1f}s", minimal=True)
            return layers
        finally:
            prep.cleanup()

    def _save_to_db(self, prep: LayerPreppedVolume, layers: np.ndarray) -> None:
        if layers.shape != (prep.depth, prep.height, prep.width):
            raise ValueError(
                f"Expected layers shape {(prep.depth, prep.height, prep.width)}, "
                f"got {layers.shape}"
            )

        t0 = time.perf_counter()
        seg = ModelSegmentation.get_or_create(
            self.session,
            match_by={
                "ImageInstanceID": prep.image_instance_id,
                "ModelID": self.model.ModelID,
            },
            update_values={
                "Depth": prep.depth,
                "Height": prep.height,
                "Width": prep.width,
                "SparseAxis": 0,
                "ScanIndices": list(range(prep.depth)),
                "DataType": self.datatype,
                "DataRepresentation": self.data_representation,
                "Threshold": None,
            },
        )
        _log(
            f"save: get_or_create ModelSegmentation in {time.perf_counter() - t0:.1f}s",
            minimal=True,
        )
        try:
            t_write = time.perf_counter()
            seg.write_data(layers)
            _log(
                f"save: zarr write {layers.shape} in {time.perf_counter() - t_write:.1f}s",
                minimal=True,
            )
        finally:
            t_flush = time.perf_counter()
            self.session.flush()
            self.session.expunge(seg)
            _log(f"save: flush in {time.perf_counter() - t_flush:.1f}s", minimal=True)
        t_commit = time.perf_counter()
        self.session.commit()
        _log(
            f"save: commit + total {time.perf_counter() - t0:.1f}s",
            minimal=True,
        )

    def filter_image_ids(self, image_ids: Iterable[int]) -> Set[int]:
        image_ids_set = set(image_ids)
        existing = set(
            ModelSegmentation.select(
                self.session,
                "ImageInstanceID",
                ImageInstanceID=image_ids_set,
                ModelID=self.model.ModelID,
                distinct=True,
            )
        )
        if existing:
            print(f"Skipping {len(existing)} images with existing layer segmentation")
        return image_ids_set - existing

    def run(self, image_ids: Iterable[int]) -> None:
        """Run preprocess → nnU-Net → save for each image."""
        t_model = time.perf_counter()
        self._ensure_predictor()
        _log(f"model ready in {time.perf_counter() - t_model:.1f}s", minimal=True)

        failed: list[int] = []
        for instance in tqdm(
            ImageInstance.by_ids(self.session, set(image_ids)),
            desc="Layer segmentation",
        ):
            image_id = instance.ImageInstanceID
            prep: LayerPreppedVolume | None = None
            t_image = time.perf_counter()
            try:
                t_load = time.perf_counter()
                volume = instance.pixel_array
                _log(
                    f"image {image_id}: pixel_array {volume.shape} "
                    f"in {time.perf_counter() - t_load:.1f}s",
                    minimal=True,
                )

                prep = self._prep_volume(
                    volume,
                    image_instance_id=image_id,
                )
                self._run_nnunet(prep)
                layers = self.masks_to_array(prep)
                self._save_to_db(prep, layers)
                _log(
                    f"image {image_id}: done in {time.perf_counter() - t_image:.1f}s",
                    minimal=True,
                )
            except Exception as e:
                failed.append(image_id)
                print(
                    f"Layer segmentation failed for image {image_id}: {e}",
                    flush=True,
                )
            finally:
                if prep is not None:
                    prep.cleanup()

        if failed:
            raise RuntimeError(
                f"Layer segmentation failed for {len(failed)} image(s): {failed}"
            )


def run_for_image_ids(
    session,
    image_ids: Iterable[int],
    *,
    device: torch.device | None = None,
    overwrite: bool = False,
) -> None:
    """Entry point for CLI and RQ worker (``layer-segmentation`` queue)."""
    image_ids = set(image_ids)
    processor = LayerSegmentation(session, device=device or auto_device())
    if overwrite:
        filtered = image_ids
        print(f"Processing {len(filtered)} images (overwrite)")
    else:
        filtered = processor.filter_image_ids(image_ids)
        print(f"Processing {len(filtered)} images (after filtering existing)")
    if not filtered:
        print("No images to process")
        return
    processor.run(filtered)
    print(f"Completed processing {len(filtered)} images")


def predict_volume(
    volume: LayerVolumeInput,
    *,
    device: torch.device | None = None,
) -> np.ndarray:
    """In-process layer prediction (no DB). ``volume`` is uint8 ``(D, H, W)`` or a ``.npy`` path."""
    return LayerSegmentation(session=None, device=device).predict_volume(
        load_layer_volume(volume)
    )
