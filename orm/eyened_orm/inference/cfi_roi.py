from typing import Any, Dict

from rtnls_fundusprep.mask_extraction import get_cfi_bounds

from eyened_orm import AttributeDataType
from eyened_orm.inference.model_versions import package_distribution_version
from eyened_orm.inference.outputs import AttributeOutput
from eyened_orm.inference.pipeline import InferenceItem, Pipeline

FUNDUSPREP_DISTRIBUTION = "retinalysis-fundusprep"


class CFI_ROI(Pipeline):
    """CFI ROI detection: fundus circle bounds (OpenCV, no torch)."""

    output = AttributeOutput(
        model_name="CFI_ROI",
        attribute_name="CFI_ROI",
        data_type=AttributeDataType.JSON,
        version=package_distribution_version(FUNDUSPREP_DISTRIBUTION),
        description="https://github.com/Eyened/retinalysis-fundusprep",
    )
    needs_torch = False

    def preprocess(self, item: InferenceItem) -> Dict[str, Any]:
        return get_cfi_bounds(item.image).to_dict_all()
