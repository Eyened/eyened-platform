from typing import Any, Iterator, Iterable, List, Set, Tuple

import torch
import numpy as np
from tqdm import tqdm

from eyened_orm import (
    AttributesModel,
    AttributeDefinition,
    AttributeDataType,
    AttributeValue,
    ImageInstance,
)
from eyened_orm.inference.multi_process_inference import (
    BaseInferencePipeline,
    MultiProcessInference,
)


class AttributeInferencePipeline(BaseInferencePipeline):
    """Base class for inference pipelines that produce attribute values.

    Subclasses should define:
    - model_name: str - name of the AttributesModel
    - model_version: str - version of the AttributesModel (or set in __init__)
    - model_description: Optional[str] - description for model creation
    - attribute_name: str - name of the AttributeDefinition
    - attribute_data_type: AttributeDataType - data type (JSON, Float, etc.)

    Subclasses can override:
    - _load_models() - called before processing starts
    - filter_image_ids(image_ids) - filter/skip existing (return filtered set)
    - _save_result(image_id, result) - customize how results are saved
    - _normalize_device() - customize device initialization
    """

    # Subclasses should define these class attributes
    model_name: str
    model_version: str = "1.0"
    model_description: str = ""
    attribute_name: str
    attribute_data_type: AttributeDataType

    def __init__(
        self,
        session,
        n_workers: int = 8,
        **kwargs,
    ):
        """Initialize the inference pipeline.

        Args:
            session: Database session
            n_workers: Number of preprocessing worker processes
            **kwargs: Additional arguments stored as instance attributes
        """
        self.session = session
        self.n_workers = n_workers

        # Store any additional kwargs as instance attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Create or retrieve AttributesModel
        self.model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": self.model_name, "Version": self.model_version},
            create_kwargs={"Description": self.model_description},
        )

        # Create or retrieve AttributeDefinition
        self.attr_definition = AttributeDefinition.get_or_create(
            session,
            match_by={
                "AttributeName": self.attribute_name,
                "AttributeDataType": self.attribute_data_type,
            },
        )

        # Track if models have been loaded
        self._models_loaded = False

    def _load_models(self) -> None:
        """Load models before processing. Override in subclasses that need model loading."""
        pass

    def _ensure_models_loaded(self) -> None:
        """Ensure models are loaded (only loads once)."""
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True

    def _save_result(self, image_id: int, result: Any) -> None:
        """Save result to database. Override for custom saving logic.

        Args:
            image_id: Image instance ID
            result: Result to save
        """
        # Determine which value field to use based on attribute data type
        if self.attribute_data_type == AttributeDataType.JSON:
            update_values = {"ValueJSON": result}
        elif self.attribute_data_type == AttributeDataType.Float:
            update_values = {"ValueFloat": result}
        else:
            # Fallback to JSON for other types
            update_values = {"ValueJSON": result}

        AttributeValue.upsert(
            self.session,
            match_by={
                "AttributeID": self.attr_definition.AttributeID,
                "ModelID": self.model.ModelID,
                "ImageInstanceID": image_id,
            },
            update_values=update_values,
        )

    def _prepare_torch_batch(
        self,
        prep_batch: List[Any],
    ) -> torch.Tensor:
        """Prepare preprocessed batch for torch processing.

        Args:
            prep_batch: List of preprocessed items (should be tuples of (_, image_array))

        Returns:
            Torch tensor ready for model forward pass
        """
        x_np = np.stack([x_im.transpose(2, 0, 1) for _, x_im in prep_batch], axis=0)
        return torch.from_numpy(x_np).to(device=self.device, dtype=torch.float32)

    def _run_torch_forward(
        self,
        x_in: torch.Tensor,
        model_forward_fn,
    ) -> np.ndarray:
        """Run torch model forward pass.

        Args:
            x_in: Input torch tensor
            model_forward_fn: Function that takes torch tensor and returns model output

        Returns:
            Model output as numpy array
        """
        with torch.no_grad():
            return model_forward_fn(x_in).detach().cpu().numpy()

    def filter_image_ids(self, image_ids: Iterable[int]) -> Set[int]:
        """Filter out image IDs that already have results.

        Args:
            image_ids: Iterable of image IDs to filter

        Returns:
            Set of image IDs that don't have existing results
        """
        image_ids_set = set(image_ids)

        existing_ids = set(
            AttributeValue.select(
                self.session,
                "ImageInstanceID",
                AttributeID=self.attr_definition.AttributeID,
                ModelID=self.model.ModelID,
                ImageInstanceID=image_ids_set,
            )
        )
        if existing_ids:
            print(f"Skipping {len(existing_ids)} existing images")
        return image_ids_set - existing_ids

    def process(self, image_ids: Iterable[int]) -> Iterator[Tuple[int, Any]]:
        """Process images and yield (image_id, result) tuples.

        Args:
            image_ids: Iterable of image instance IDs to process

        Yields:
            Tuples of (image_id, result) for each processed image
        """
        self._ensure_models_loaded()

        image_ids_set = set(image_ids)
        if not image_ids_set:
            return

        # Fetch images from database
        images = ImageInstance.by_ids(self.session, image_ids_set)
        items = [(iid, image.path) for iid, image in images.items()]

        mpi = MultiProcessInference(
            items,
            pipeline=self,
            n_workers=self.n_workers,
            batch_size=getattr(self, "batch_size", 1),
        )
        yield from mpi.run()

    def run(self, image_ids: Iterable[int], commit_interval: int = 100) -> None:
        """Run inference on a list of image IDs and save results.

        Args:
            image_ids: Iterable of image instance IDs to process
        """

        # Process results
        image_ids_set = set(image_ids)
        for i, (image_id, result) in enumerate(tqdm(
            self.process(image_ids_set), total=len(image_ids_set)
        )):
            if i % commit_interval == 0:
                self.session.commit()
            if result is None:
                print(f"Image {image_id} failed to process")
                continue
            self._save_result(image_id, result)
        self.session.commit()