from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Iterable, Iterator, List, Set, Tuple

import numpy as np
from tqdm import tqdm

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributeValue,
    ImageInstance,
    Modality,
)
from eyened_orm.inference.model_inputs import (
    ModelInputSpec,
    attribute_value_data,
    register_model_inputs,
    register_model_output,
    resolve_inputs_for_images,
)
from eyened_orm.inference.multi_process_inference import (
    BaseInferencePipeline,
    MultiProcessInference,
)


@dataclass(frozen=True)
class InferenceItem:
    """Picklable worker payload: decoded pixels and optional resolved input data."""

    image_rgb: np.ndarray | None
    input_values: dict[str, Any] | None = None


class AttributeInferencePipeline(BaseInferencePipeline):
    """Base class for inference pipelines that produce attribute values.

    Subclasses should define:
    - model_name: str - name of the AttributesModel
    - model_version: str - version of the AttributesModel (or set in __init__)
    - model_description: Optional[str] - description for model creation
    - attribute_name: str - name of the AttributeDefinition
    - attribute_data_type: AttributeDataType - data type (JSON, Float, etc.)
    - required_inputs: tuple of ModelInputSpec for input dependencies

    Subclasses can override:
    - _load_models() - called before processing starts
    - filter_image_ids(image_ids) - filter/skip existing (return filtered set)
    - _save_result(image_id, result) - customize how results are saved

    PyTorch-based pipelines should subclass :class:`TorchAttributeInferencePipeline`
    instead (so environments without torch can import this module).
    """

    # Subclasses should define these class attributes
    model_name: str
    model_version: str = "1.0"
    model_description: str = ""
    attribute_name: str
    attribute_data_type: AttributeDataType
    supported_modalities: ClassVar[tuple[Modality, ...]] = ()
    required_inputs: ClassVar[tuple[ModelInputSpec, ...]] = ()

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
        self._input_values_by_image: dict[int, dict[str, AttributeValue]] = {}

        # Store any additional kwargs as instance attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Create or retrieve AttributesModel; sync Description on each run (see layer_segmentation / cfi_amd).
        self.model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": self.model_name, "Version": self.model_version},
            update_values={"Description": self.model_description},
        )

        # Create or retrieve AttributeDefinition
        self.attr_definition = AttributeDefinition.get_or_create(
            session,
            match_by={
                "AttributeName": self.attribute_name,
                "AttributeDataType": self.attribute_data_type,
            },
        )

        self._register_model_io()

        # Track if models have been loaded
        self._models_loaded = False

    def _register_model_io(self) -> None:
        """Register declared model outputs and inputs in the database."""
        register_model_output(self.session, self.model, self.attr_definition)
        register_model_inputs(self.session, self.model, self.required_inputs)

    def _load_models(self) -> None:
        """Load models before processing. Override in subclasses that need model loading."""
        pass

    def _ensure_models_loaded(self) -> None:
        """Ensure models are loaded (only loads once)."""
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True

    def _save_result(self, image_id: int, result: Any) -> None:
        """Save result to database and link input provenance when available."""
        if self.attribute_data_type == AttributeDataType.JSON:
            update_values = {"ValueJSON": result}
        elif self.attribute_data_type == AttributeDataType.Float:
            update_values = {"ValueFloat": result}
        else:
            update_values = {"ValueJSON": result}

        av = AttributeValue.upsert(
            self.session,
            match_by={
                "AttributeID": self.attr_definition.AttributeID,
                "ModelID": self.model.ModelID,
                "ImageInstanceID": image_id,
            },
            update_values=update_values,
        )

        input_values = self._input_values_by_image.get(image_id)
        if input_values:
            av.InputValues = set(input_values.values())
            self.session.add(av)

    def _ensure_inputs_resolved(self, image_ids: Iterable[int]) -> None:
        if not self.required_inputs:
            self._input_values_by_image = {}
            return
        self._input_values_by_image = resolve_inputs_for_images(
            self.session, set(image_ids), self.required_inputs
        )

    def _filter_images_with_required_inputs(
        self, image_ids: Iterable[int]
    ) -> Set[int]:
        if not self.required_inputs:
            return set(image_ids)

        ready: set[int] = set()
        missing = 0
        for image_id in image_ids:
            inputs = self._input_values_by_image.get(image_id, {})
            if not all(
                spec.resolved_input_name in inputs for spec in self.required_inputs
            ):
                missing += 1
                continue
            ready.add(image_id)
        if missing:
            print(f"Skipping {missing} images missing required inputs")
        return ready

    def filter_image_ids(self, image_ids: Iterable[int]) -> Set[int]:
        """Filter out image IDs that already have results."""
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

        pending = image_ids_set - existing_ids
        if self.required_inputs:
            self._ensure_inputs_resolved(pending)
            pending = self._filter_images_with_required_inputs(pending)
        else:
            self._input_values_by_image = {}

        return pending

    def _input_data_for_image(self, image_id: int) -> dict[str, Any] | None:
        """Plain input values for worker processes (ORM objects stay in the parent)."""
        if not self.required_inputs:
            return None
        inputs = self._input_values_by_image.get(image_id)
        if not inputs:
            return None
        return {
            name: attribute_value_data(av) for name, av in inputs.items()
        }

    def _load_image_rgb(self, image: ImageInstance) -> np.ndarray:
        """Load decoded pixels for one image. Override in modality-specific subclasses."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement _load_image_rgb"
        )

    def _build_preprocess_items(
        self, images: list[ImageInstance]
    ) -> list[tuple[int, InferenceItem | None]]:
        items: list[tuple[int, InferenceItem | None]] = []
        for img in images:
            try:
                image_rgb = self._load_image_rgb(img)
                items.append(
                    (
                        img.ImageInstanceID,
                        InferenceItem(
                            image_rgb=image_rgb,
                            input_values=self._input_data_for_image(
                                img.ImageInstanceID
                            ),
                        ),
                    )
                )
            except Exception as exc:
                print(f"Failed to load image {img.ImageInstanceID}: {exc}")
                items.append((img.ImageInstanceID, None))
        return items

    def process(self, image_ids: Iterable[int]) -> Iterator[Tuple[int, Any]]:
        """Process images and yield (image_id, result) tuples."""
        self._ensure_models_loaded()

        image_ids_set = set(image_ids)
        if not image_ids_set:
            return

        self._ensure_inputs_resolved(image_ids_set)

        images = ImageInstance.by_ids(self.session, image_ids_set)
        items = self._build_preprocess_items(images)

        mpi = MultiProcessInference(
            items,
            pipeline=self,
            n_workers=self.n_workers,
            batch_size=getattr(self, "batch_size", 1),
        )
        yield from mpi.run()

    def run(self, image_ids: Iterable[int], commit_interval: int = 100) -> None:
        """Run inference on a list of image IDs and save results."""
        image_ids_set = set(image_ids)
        for i, (image_id, result) in enumerate(
            tqdm(self.process(image_ids_set), total=len(image_ids_set))
        ):
            if i % commit_interval == 0:
                self.session.commit()
            if result is None:
                print(f"Image {image_id} failed to process")
                continue
            self._save_result(image_id, result)
        self.session.commit()


class CFIAttributeInferencePipeline(AttributeInferencePipeline):
    """Color fundus attribute pipelines: load pixels via the ORM data-access layer."""

    def _load_image_rgb(self, image: ImageInstance) -> np.ndarray:
        from eyened_orm.inference.utils import load_fundus_rgb

        return load_fundus_rgb(image)


class TorchAttributeInferencePipeline(CFIAttributeInferencePipeline):
    """Attribute pipeline that runs PyTorch models (imports ``torch`` only when used)."""

    def _prepare_torch_batch(self, prep_batch: List[Any]) -> Any:
        """Prepare preprocessed batch for torch processing."""
        import torch

        x_np = np.stack([x_im.transpose(2, 0, 1) for _, x_im in prep_batch], axis=0)
        return torch.from_numpy(x_np).to(device=self.device, dtype=torch.float32)

    def _run_torch_forward(self, x_in: Any, model_forward_fn) -> np.ndarray:
        import torch

        with torch.no_grad():
            return model_forward_fn(x_in).detach().cpu().numpy()
