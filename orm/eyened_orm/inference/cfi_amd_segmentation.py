from os import PathLike
from typing import Any, Iterable, List, Tuple, Dict, Set, Iterator

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


class CFI_AMD(BaseInferencePipeline):
    """CFI AMD segmentation pipeline - detects drusen, RPD, hyperpigmentation, and RPE degeneration."""

    # keys of the model output dictionary
    model_output_keys = {"drusen", "RPD", "hyperpigmentation", "rpe_degeneration"}
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
        session,
        device: torch.device,
        n_workers: int = 12,
        batch_size: int = 8,
        save_only_above_threshold: bool = True,
        undo_transform: bool = True,
    ):
        self.session = session
        self.n_workers = n_workers
        self.batch_size = batch_size
        self.device = device
        self.save_only_above_threshold = save_only_above_threshold
        self.undo_transform = undo_transform

        # Track if models have been loaded
        self._models_loaded = False

        # Create or retrieve Features
        self.features = {
            output_key: Feature.get_or_create(
                session, match_by={"FeatureName": feature_name}
            )
            for output_key, feature_name in self.feature_names.items()
        }

        # Create or retrieve SegmentationModels
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
            for output_key, (name, version, description) in self.model_configs.items()
        }

    def _load_models(self) -> None:
        """Load the CFI AMD processor."""
        from cfi_amd.processor import Processor

        self.processor = Processor(self.device)

    def _ensure_models_loaded(self) -> None:
        """Ensure models are loaded (only loads once)."""
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True

    def _get_model_segmentation(
        self, instance_id: int, model: SegmentationModel, h: int, w: int
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
            },
        )

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

        m = self._get_model_segmentation(image_id, model, h=h, w=w)
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
        items = [(iid, image.path) for iid, image in images.items()]

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
                if output_key not in self.models:
                    continue

                yield image_id, self.models[output_key], segmentation_array

    def filter_image_ids(self, image_ids: Iterable[int]) -> Set[int]:
        """Filter out image IDs that already have all required segmentations.

        Args:
            image_ids: Iterable of image IDs to filter

        Returns:
            Set of image IDs that don't have all required segmentations
        """
        image_ids_set = set(image_ids)

        # Get all existing ModelSegmentation records for these images and models
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
            self._save_result(image_id, model, segmentation_array)
