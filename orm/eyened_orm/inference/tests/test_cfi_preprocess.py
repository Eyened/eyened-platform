"""Tests for shared CFI preprocessing."""

from __future__ import annotations

import numpy as np

from eyened_orm.inference.cfi_preprocess import crop_fundus_from_roi
from rtnls_fundusprep.cfi_bounds import CFIBounds


def test_crop_fundus_from_roi_uses_stored_bounds():
    image = np.zeros((128, 128, 3), dtype=np.uint8)
    image[32:96, 32:96] = 200
    bounds = CFIBounds.full_frame(image)
    roi_dict = bounds.to_dict_all()

    result = crop_fundus_from_roi(image, roi_dict, resize=64, apply_ce=False)
    assert result is not None
    transform, tensor = result
    assert tensor.shape == (64, 64, 3)
    assert transform is not None


def test_crop_fundus_from_roi_returns_none_without_roi():
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    assert crop_fundus_from_roi(image, None, resize=32) is None
