"""Shared CFI fundus cropping for inference pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from eyened_orm.inference.utils import normalize


@dataclass(frozen=True)
class PreprocessItem:
    """Picklable worker payload: decoded RGB + optional stored CFI_ROI dict."""

    image_rgb: np.ndarray | None
    roi_dict: dict | None = None


def roi_dict_usable(roi_dict: dict | None) -> bool:
    if roi_dict is None:
        return False
    return roi_dict.get("success") is not False


def bounds_from_roi_dict(
    roi_dict: dict,
    image_rgb: np.ndarray,
    *,
    hw: tuple[int | None, int | None] | None = None,
):
    from rtnls_fundusprep.cfi_bounds import CFIBounds

    payload = dict(roi_dict)
    if hw is not None and "hw" not in payload:
        payload["hw"] = hw
    return CFIBounds(**payload, image=image_rgb)


def crop_fundus_from_roi(
    image_rgb: np.ndarray,
    roi_dict: dict | None,
    *,
    resize: int,
    apply_ce: bool = False,
    hw: tuple[int | None, int | None] | None = None,
) -> tuple[Any, np.ndarray] | None:
    """Crop and normalize a fundus image using a stored CFI_ROI attribute."""
    if not roi_dict_usable(roi_dict):
        return None
    bounds = bounds_from_roi_dict(roi_dict, image_rgb, hw=hw)
    transform, bounds_cropped = bounds.crop(resize)
    image = bounds_cropped.image
    contrast = bounds_cropped.contrast_enhanced_5 if apply_ce else None
    return transform, normalize(image, contrast)
