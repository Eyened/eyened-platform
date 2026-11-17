import numpy as np
from rtnls_inference.ensembles import HeatmapRegressionEnsemble

from eyened_orm import AttributeDataType
from eyened_orm.inference.cfi_preprocess import cfi_roi_from_input_values, crop_fundus_from_roi
from eyened_orm.inference.model_inputs import CFI_ROI_INPUT
from eyened_orm.inference.model_versions import huggingface_pipeline_version
from eyened_orm.inference.outputs import AttributeOutput
from eyened_orm.inference.pipeline import Pipeline

FOVEA_ARTIFACT = "Eyened/vascx:fovea/fovea_july24.pt"
DISCEDGE_ARTIFACT = "Eyened/vascx:discedge/discedge_july24.pt"


def extract_max_keypoint(heatmap):
    """``(y, x)`` of the maximum of a ``(h, w)`` or ``(1, h, w)`` heatmap."""
    if len(heatmap.shape) == 3:
        heatmap = heatmap[0]
    return np.unravel_index(heatmap.argmax(), heatmap.shape)


def get_coordinate(T, heatmap):
    """Transform keypoint coordinate from resized to original image coordinates."""
    y, x = extract_max_keypoint(heatmap)
    x, y = T.apply_inverse([[x + 0.5, y + 0.5]])[0]  # + 0.5 to center the pixel
    return (float(x), float(y))


class CFIKeypoints(Pipeline):
    """Fovea and disc edge locations, in original image pixels."""

    output = AttributeOutput(
        model_name="CFI_Keypoints",
        attribute_name="CFI_Keypoints",
        data_type=AttributeDataType.JSON,
        version=huggingface_pipeline_version(FOVEA_ARTIFACT, DISCEDGE_ARTIFACT),
        description="https://github.com/Eyened/retinalysis-inference Eyened/vascx:fovea Eyened/vascx:discedge",
    )
    inputs = (CFI_ROI_INPUT,)
    resize = 512

    def load(self) -> None:
        self.ensembles = {}
        for name, artifact in (("fovea", FOVEA_ARTIFACT), ("discedge", DISCEDGE_ARTIFACT)):
            ensemble = HeatmapRegressionEnsemble.from_huggingface(artifact).to(self.device)
            transform = ensemble.config["datamodule"]["test_transform"]
            assert transform["resize"] == self.resize and transform["contrast_enhance"]
            self.ensembles[name] = ensemble

    def preprocess(self, item):
        roi = cfi_roi_from_input_values(item.input_values)
        return crop_fundus_from_roi(item.image, roi, resize=self.resize, apply_ce=True)

    def process_batch(self, prep_batch):
        # (batch, n_models, 1, h, w) -> ensemble mean per keypoint
        fovea = self.forward(self.ensembles["fovea"], prep_batch).mean(axis=1)
        discedge = self.forward(self.ensembles["discedge"], prep_batch).mean(axis=1)
        return zip(fovea, discedge)

    def postprocess(self, prep, heatmaps) -> dict:
        T, _ = prep
        fovea, discedge = heatmaps
        return {
            "fovea_xy": get_coordinate(T, fovea),
            "disc_edge_xy": get_coordinate(T, discedge),
        }
