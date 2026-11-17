import numpy as np
from rtnls_inference import RegressionEnsemble

from eyened_orm import AttributeDataType
from eyened_orm.inference.cfi_preprocess import cfi_roi_from_input_values, crop_fundus_from_roi
from eyened_orm.inference.model_inputs import CFI_ROI_INPUT
from eyened_orm.inference.model_versions import huggingface_artifact_version
from eyened_orm.inference.outputs import AttributeOutput
from eyened_orm.inference.pipeline import Pipeline

HF_ARTIFACT = "Eyened/vascx:odfd/odfd_march25.pt"


class CFI_ODFD(Pipeline):
    """Optic disc to fovea distance, in original image pixels."""

    output = AttributeOutput(
        model_name="CFI_ODFD",
        attribute_name="CFI_ODFD",
        data_type=AttributeDataType.Float,
        version=huggingface_artifact_version(HF_ARTIFACT),
        description=HF_ARTIFACT,
    )
    inputs = (CFI_ROI_INPUT,)
    resize = 512

    def load(self) -> None:
        self.ensemble = RegressionEnsemble.from_huggingface(HF_ARTIFACT).to(self.device)
        assert self.ensemble.config["datamodule"]["test_transform"]["resize"] == self.resize

    def preprocess(self, item):
        roi = cfi_roi_from_input_values(item.input_values)
        return crop_fundus_from_roi(item.image, roi, resize=self.resize)

    def process_batch(self, prep_batch):
        # (n_models, batch, 1) -> ensemble mean of the single channel
        return self.forward(self.ensemble, prep_batch).mean(axis=0)[:, 0]

    def postprocess(self, prep, distance: float) -> float:
        T, _ = prep
        # Map a horizontal segment of that length back to the original image.
        p0, p1 = T.apply_inverse(((0, 0), (self.resize * distance, 0)))
        return float(np.linalg.norm(p1 - p0))
