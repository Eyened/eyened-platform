from typing import Any, Iterable, List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from eyened_orm import AttributeDataType, Modality
from eyened_orm.inference.attribute_inference import TorchAttributeInferencePipeline
from eyened_orm.inference.cfi_preprocess import PreprocessItem, crop_fundus_from_roi
from eyened_orm.inference.model_inputs import ModelInputSpec
from rtnls_inference import ClassificationEnsemble


def logits_to_continuous_score(logits, temperature=3.0):
    """Convert classification logits to continuous quality score."""
    logits = torch.tensor(logits, dtype=torch.float32) / temperature
    probs = F.softmax(logits, dim=-1)
    num_classes = len(logits)
    class_indices = torch.arange(num_classes, dtype=torch.float32).flip(dims=[0])
    continuous_score = torch.sum(probs * class_indices).item()
    return continuous_score


class CFI_Quality(TorchAttributeInferencePipeline):
    """CFI image quality assessment pipeline."""

    model_name = "CFI_Quality"
    model_version = "1.0"
    model_description = "Eyened/vascx:quality"
    attribute_name = "CFI_Quality"
    attribute_data_type = AttributeDataType.Float
    supported_modalities = (Modality.ColorFundus,)
    required_inputs = (
        ModelInputSpec(
            "CFI_ROI",
            "CFI_ROI",
            "1.0",
            attribute_data_type=AttributeDataType.JSON,
        ),
    )

    def __init__(
        self,
        session,
        device: torch.device,
        n_workers: int = 8,
        batch_size: int = 8,
        **kwargs,
    ):
        super().__init__(
            session, n_workers=n_workers, batch_size=batch_size, device=device
        )
        self.resize: Optional[int] = None
        self.ensemble: Optional[ClassificationEnsemble] = None

    def _load_models(self) -> None:
        """Load quality assessment ensemble model."""
        self.ensemble = ClassificationEnsemble.from_huggingface(
            "Eyened/vascx:quality/quality.pt"
        ).to(self.device)

        assert self.ensemble.config["datamodule"]["test_transform"]["resize"] == 224
        self.resize = 224

    def preprocess(self, item: PreprocessItem | None) -> Tuple[Any, np.ndarray] | None:
        """Preprocess image for quality assessment using stored CFI_ROI."""
        if item is None or item.image_rgb is None:
            return None
        return crop_fundus_from_roi(
            item.image_rgb,
            item.roi_dict,
            resize=self.resize,
            apply_ce=False,
        )

    def process_batch(
        self, prep_batch: List[Tuple[Any, np.ndarray]]
    ) -> Iterable[np.ndarray]:
        """Process batch: ensemble averaging."""
        x_in = self._prepare_torch_batch(prep_batch)
        result = self._run_torch_forward(x_in, self.ensemble.forward)

        # Ensemble averaging: result is (num_models, batch_size, num_classes)
        # Average over ensemble dimension (dim=0) to get (batch_size, num_classes)
        return result.mean(axis=0)

    def postprocess(
        self, prep_item: Tuple[Any, np.ndarray], batch_output: np.ndarray
    ) -> float:
        return logits_to_continuous_score(batch_output)
