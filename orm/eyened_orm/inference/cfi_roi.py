from typing import Any, Dict, Optional

import numpy as np

from eyened_orm import AttributeDataType, Modality
from eyened_orm.inference.attribute_inference import (
    CFIAttributeInferencePipeline,
    InferenceItem,
)
from eyened_orm.inference.model_versions import package_distribution_version

from rtnls_fundusprep.mask_extraction import get_cfi_bounds

FUNDUSPREP_DISTRIBUTION = "retinalysis-fundusprep"


class CFI_ROI(CFIAttributeInferencePipeline):
    """CFI ROI detection pipeline - extracts CFI bounds from fundus images."""

    model_name = "CFI_ROI"
    model_description = "https://github.com/Eyened/retinalysis-fundusprep"
    attribute_name = "CFI_ROI"
    attribute_data_type = AttributeDataType.JSON
    supported_modalities = (Modality.ColorFundus,)

    def __init__(self, session, n_workers: int = 8, **kwargs):
        self.model_version = package_distribution_version(FUNDUSPREP_DISTRIBUTION)
        super().__init__(session, n_workers=n_workers)

    def preprocess(self, item: InferenceItem | None) -> Optional[Dict[str, Any]]:
        if item is None or item.image_rgb is None:
            return None
        try:
            bounds = get_cfi_bounds(item.image_rgb)
            return bounds.to_dict_all()
        except Exception as exc:
            print(f"CFI_ROI preprocessing failed: {exc}")
            return None
