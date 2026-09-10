import os
import shutil
import tempfile
import time
from os import PathLike
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Set, Tuple, Union

import numpy as np
import torch
from tqdm import tqdm

from eyened_orm import (
    Feature,
    SegmentationModel,
    ModelSegmentation,
    ImageInstance,
    DataRepresentation,
    Datatype,
)
from eyened_orm.inference.multi_process_inference import (
    BaseInferencePipeline,
    MultiProcessInference,
)


def _log(msg: str, *, minimal: bool = False) -> None:
    from eyened_orm.inference.utils import inference_verbose

    if minimal or inference_verbose():
        print(f"[cfi-amd] {msg}", flush=True)


def image_projection_matrix_from_cfi_roi(image: ImageInstance) -> List[List[float]]:
    """Segmentation→image matrix from stored CFI_ROI bounds (1024-crop)."""
    matrix = image.cropping_matrix_inverse
    if matrix is None:
        raise ValueError(
            f"ImageInstance {image.ImageInstanceID} has no CFI_ROI bounds; "
            "cannot store native-resolution segmentation"
        )
    return np.asarray(matrix, dtype=float).tolist()


def cfi_amd_maps_only(result: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """Drop non-array entries (e.g. ``bounds``) so npz round-trips without pickle."""
    maps: Dict[str, np.ndarray] = {}
    for key in CFI_AMD.model_output_keys:
        if key not in result:
            raise KeyError(f"Missing CFI AMD output {key!r}, got {list(result.keys())}")
        arr = np.asarray(result[key])
        if arr.dtype == object:
            raise TypeError(f"CFI AMD output {key!r} is not a numeric array")
        maps[key] = arr
    return maps


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


class CFI_AMD(BaseInferencePipeline):
    """CFI AMD segmentation pipeline - detects drusen, RPD, hyperpigmentation, and RPE degeneration."""

    # keys of the model output dictionary
    model_output_keys = frozenset(
        {"drusen", "RPD", "hyperpigmentation", "rpe_degeneration"}
    )
    # feature names in the database
    feature_names = {
        "drusen": "Drusen",
        "RPD": "Reticular pseudodrusen",
        "hyperpigmentation": "RPE hyperpigmentation",
        "rpe_degeneration": "Retinal pigment epithelium (RPE) degeneration",
    }
    # (model_name, model_version, model_description)
    model_configs = {
        "drusen": ("Drusen", "3", "https://github.com/Eyened/cfi-amd"),
        "RPD": ("Reticular pseudodrusen", "3", "https://github.com/Eyened/cfi-amd"),
        "hyperpigmentation": (
            "Hyperpigmentation",
            "3",
            "https://github.com/Eyened/cfi-amd",
        ),
        "rpe_degeneration": (
            "RPE degeneration",
            "3",
            "https://github.com/Eyened/cfi-amd",
        ),
    }
    data_representation = DataRepresentation.Probability
    datatype = Datatype.R8
    threshold = 0.5

    def __init__(
        self,
        session=None,
        device: torch.device | None = None,
        n_workers: int = 12,
        batch_size: int = 8,
        save_only_above_threshold: bool = True,
        undo_transform: bool = True,
    ):
        from eyened_orm.inference.utils import auto_device

        self.session = session
        self.n_workers = n_workers
        self.batch_size = batch_size
        self.device = device if device is not None else auto_device()
        self.save_only_above_threshold = save_only_above_threshold
        self.undo_transform = undo_transform
        self._models_loaded = False
        self.features: Dict[str, Feature] | None = None
        self.models: Dict[str, SegmentationModel] | None = None

        if session is not None:
            self.features = {
                output_key: Feature.get_or_create(
                    session, match_by={"FeatureName": feature_name}
                )
                for output_key, feature_name in self.feature_names.items()
            }
            self.models = {
                output_key: SegmentationModel.get_or_create(
                    session,
                    match_by={
                        "FeatureID": self.features[output_key].FeatureID,
                        "ModelName": name,
                        "Version": version,
                    },
                    update_values={"Description": description},
                )
                for output_key, (
                    name,
                    version,
                    description,
                ) in self.model_configs.items()
            }

    def _load_models(self) -> None:
        """Load the CFI AMD processor."""
        from cfi_amd.processor import Processor

        from eyened_orm.inference.utils import assert_cuda_kernel_compatible

        if self.device.type == "cuda":
            assert_cuda_kernel_compatible(self.device)
        models_dir = os.environ.get("CFI_AMD_MODELS_DIR")
        self.processor = Processor(self.device, models_dir=models_dir)

    def _ensure_models_loaded(self) -> None:
        """Ensure models are loaded (only loads once)."""
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True

    def _get_model_segmentation(
        self,
        instance_id: int,
        model: SegmentationModel,
        h: int,
        w: int,
        image_projection_matrix: List[List[float]] | None = None,
    ) -> ModelSegmentation:
        return ModelSegmentation.get_or_create(
            self.session,
            match_by={
                "ImageInstanceID": instance_id,
                "ModelID": model.ModelID,
            },
            update_values={
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

    def predict_path(self, image_path: PathLike[str]) -> Dict[str, np.ndarray]:
        """Run preprocess → model → postprocess (no database)."""
        t0 = time.perf_counter()
        self._ensure_models_loaded()
        prep = self.preprocess(image_path)
        (batch_out,) = tuple(self.process_batch([prep]))
        out = cfi_amd_maps_only(self.postprocess(prep, batch_out))
        _log(
            f"done keys={list(out.keys())} in {time.perf_counter() - t0:.1f}s",
            minimal=True,
        )
        return out

    def _save_result(
        self, image_id: int, model: SegmentationModel, segmentation_array: np.ndarray
    ) -> None:
        """Save a single segmentation result to database.

        Args:
            image_id: Image instance ID
            model_id: Model ID for this segmentation
            segmentation_array: Segmentation array (h, w) with values in [0, 1]
        """
        h, w = segmentation_array.shape
        image_projection_matrix = None
        if not self.undo_transform:
            image = ImageInstance.by_id(self.session, image_id)
            if image is None:
                raise ValueError(f"ImageInstance {image_id} not found")
            image_projection_matrix = image_projection_matrix_from_cfi_roi(image)

        m = self._get_model_segmentation(
            image_id,
            model,
            h=h,
            w=w,
            image_projection_matrix=image_projection_matrix,
        )
        try:
            # Only save if above threshold, or always save depending on configuration
            if not self.save_only_above_threshold or np.any(
                segmentation_array >= self.threshold
            ):
                # Convert float (0-1) to uint8 (0-255) for Datatype.R8
                data = (255 * segmentation_array).astype(np.uint8)
                m.write_data(data, axis=0)
        finally:
            # Prevent the session identity map from growing without bound.
            self.session.flush()
            self.session.expunge(m)

        self.session.commit()

    def preprocess(self, image_path: PathLike[str]) -> Any:
        """Preprocess image using the processor."""
        return self.processor.preprocess(image_path)

    def process_batch(self, prep_batch: List[Any]) -> Iterable[Dict[str, np.ndarray]]:
        """Process batch using the processor."""
        return self.processor.process_batch(prep_batch)

    def postprocess(
        self, prep_item: Any, batch_output: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Postprocess results using the processor."""
        if self.undo_transform:
            return self.processor.postprocess(prep_item, batch_output)
        else:
            return batch_output

    def process(
        self, image_ids: Iterable[int]
    ) -> Iterator[Tuple[int, SegmentationModel, np.ndarray]]:
        """Process images and yield (image_id, model, segmentation_array) for each feature."""

        self._ensure_models_loaded()

        image_ids_set = set(image_ids)
        if not image_ids_set:
            return

        # Fetch images from database
        images = ImageInstance.by_ids(self.session, image_ids_set)
        items = [(image.ImageInstanceID, image.path) for image in images]

        # Use MultiProcessInference to process images
        mpi = MultiProcessInference(
            items,
            pipeline=self,
            n_workers=self.n_workers,
            batch_size=self.batch_size,
        )

        # The processor returns a dict with feature names as keys
        # Yield one result per feature per image
        for image_id, result_dict in mpi.run():
            if result_dict is None:
                continue

            for output_key, segmentation_array in result_dict.items():
                if self.models is None or output_key not in self.models:
                    continue

                yield image_id, self.models[output_key], segmentation_array

    def filter_image_ids(self, image_ids: Iterable[int]) -> Set[int]:
        """Filter out image IDs that already have all required segmentations."""
        if self.session is None or self.models is None:
            return set(image_ids)
        image_ids_set = set(image_ids)

        model_ids = {model.ModelID for model in self.models.values()}
        processed = set(
            ModelSegmentation.select(
                self.session,
                "ModelID",
                "ImageInstanceID",
                ImageInstanceID=image_ids_set,
                ModelID=model_ids,
            )
        )

        # An image is complete if it has segmentations for ALL models
        complete = {
            i
            for i in image_ids_set
            if all((model_id, i) in processed for model_id in model_ids)
        }

        if complete:
            print(f"Skipping {len(complete)} complete images")
        return image_ids_set - complete

    def run(self, image_ids: Iterable[int]) -> None:
        """Run inference on a list of image IDs and save results.

        Collects yields from process() and saves each segmentation result.

        Args:
            image_ids: Iterable of image instance IDs to process
        """
        self._ensure_models_loaded()

        image_ids_set = set(image_ids)
        if not image_ids_set:
            return

        # Stream results from process() and save them as they arrive
        total = 4 * len(image_ids_set)
        for image_id, model, segmentation_array in tqdm(
            self.process(image_ids_set), total=total
        ):
            if segmentation_array is None:
                print(f"Image {image_id}, model {model.ModelName} failed to process")
                continue
            model_name = model.ModelName
            try:
                self._save_result(image_id, model, segmentation_array)
            except ValueError as e:
                self.session.rollback()
                print(
                    f"ImageInstanceID {image_id}, model {model_name}: {e}",
                    flush=True,
                )
                continue


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
    """Entry point for CLI and RQ worker (``cfi-amd`` queue)."""
    from eyened_orm.commands.targets import iter_image_id_chunks

    image_ids = set(image_ids)
    processor = CFI_AMD(
        session,
        device=device,
        n_workers=n_workers,
        batch_size=batch_size,
        undo_transform=upscale,
    )
    total_processed = 0
    chunks = list(iter_image_id_chunks(image_ids))
    for chunk_idx, chunk in enumerate(chunks, start=1):
        if overwrite:
            filtered = chunk
        else:
            filtered = processor.filter_image_ids(chunk)
        if not filtered:
            continue
        print(
            f"Processing {len(filtered)} images "
            f"(chunk {chunk_idx}/{len(chunks)}"
            f"{', overwrite' if overwrite else ', after filtering existing'})"
        )
        processor.run(filtered)
        session.commit()
        total_processed += len(filtered)

    if total_processed == 0:
        print("No images to process")
        return
    print(f"Completed processing {total_processed} images")


def predict_image(
    image: Union[np.ndarray, PathLike[str]],
    *,
    device: torch.device | None = None,
) -> Dict[str, np.ndarray]:
    """In-process CFI AMD prediction (no DB). RGB uint8 array or image file path."""
    from eyened_orm.inference.utils import auto_device

    dev = device if device is not None else auto_device()
    processor = CFI_AMD(session=None, device=dev)
    if isinstance(image, np.ndarray):
        work = Path(tempfile.mkdtemp(prefix="cfi_amd_"))
        try:
            from PIL import Image

            path = work / "input.png"
            Image.fromarray(coerce_cfi_rgb_uint8(image)).save(path)
            return processor.predict_path(path)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return processor.predict_path(image)
