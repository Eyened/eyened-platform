from typing import Any, Dict, Optional

from eyened_orm import AttributeDataType
from eyened_orm.inference.attribute_inference import AttributeInferencePipeline
from eyened_orm.inference.utils import load_image_rgb

from rtnls_fundusprep.mask_extraction import get_cfi_bounds


class CFI_ROI(AttributeInferencePipeline):
    """CFI ROI detection pipeline - extracts CFI bounds from fundus images."""

    model_name = "CFI_ROI"
    model_version = "1.0"
    model_description = "https://github.com/Eyened/retinalysis-fundusprep"
    attribute_name = "CFI_ROI"
    attribute_data_type = AttributeDataType.JSON

    def __init__(self, session, n_workers: int = 8, **kwargs):
        super().__init__(session, n_workers=n_workers)

    def preprocess(self, image_path: Any) -> Optional[Dict[str, Any]]:
        try:
            image = load_image_rgb(image_path)
            bounds = get_cfi_bounds(image)
            return bounds.to_dict_all()
        except Exception as exc:
            print(f"CFI_ROI preprocessing failed: {exc}")
            return None
