import torch
import torch.nn.functional as F
from rtnls_inference import ClassificationEnsemble

from eyened_orm import AttributeDataType
from eyened_orm.inference.cfi_preprocess import cfi_roi_from_input_values, crop_fundus_from_roi
from eyened_orm.inference.model_inputs import CFI_ROI_INPUT
from eyened_orm.inference.model_versions import huggingface_artifact_version
from eyened_orm.inference.outputs import AttributeOutput
from eyened_orm.inference.pipeline import Pipeline

HF_ARTIFACT = "Eyened/vascx:quality/quality.pt"


def logits_to_continuous_score(logits, temperature=3.0):
    """Convert classification logits to continuous quality score."""
    logits = torch.tensor(logits, dtype=torch.float32) / temperature
    probs = F.softmax(logits, dim=-1)
    num_classes = len(logits)
    class_indices = torch.arange(num_classes, dtype=torch.float32).flip(dims=[0])
    return torch.sum(probs * class_indices).item()


class CFI_Quality(Pipeline):
    """CFI image quality score (higher is better)."""

    output = AttributeOutput(
        model_name="CFI_Quality",
        attribute_name="CFI_Quality",
        data_type=AttributeDataType.Float,
        version=huggingface_artifact_version(HF_ARTIFACT),
        description="Eyened/vascx:quality",
    )
    inputs = (CFI_ROI_INPUT,)
    resize = 224

    def load(self) -> None:
        self.ensemble = ClassificationEnsemble.from_huggingface(HF_ARTIFACT).to(self.device)
        assert self.ensemble.config["datamodule"]["test_transform"]["resize"] == self.resize

    def preprocess(self, item):
        roi = cfi_roi_from_input_values(item.input_values)
        return crop_fundus_from_roi(item.image, roi, resize=self.resize)

    def process_batch(self, prep_batch):
        # (n_models, batch, n_classes) -> ensemble mean
        return self.forward(self.ensemble, prep_batch).mean(axis=0)

    def postprocess(self, prep, logits) -> float:
        return logits_to_continuous_score(logits)
