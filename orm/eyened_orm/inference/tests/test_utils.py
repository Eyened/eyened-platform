"""Tests for CFI inference image loading helpers."""

from __future__ import annotations

import numpy as np

from eyened_orm.inference.cfi_preprocess import crop_fundus_from_roi
from eyened_orm.inference.utils import as_uint8_rgb
from rtnls_fundusprep.cfi_bounds import CFIBounds


def test_as_uint8_rgb_from_grayscale():
    gray = np.array([[0, 128], [255, 64]], dtype=np.uint8)
    rgb = as_uint8_rgb(gray)
    assert rgb.shape == (2, 2, 3)
    assert rgb.dtype == np.uint8
    np.testing.assert_array_equal(rgb[:, :, 0], gray)


def test_crop_fundus_from_stored_roi():
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[16:48, 16:48] = 180
    bounds = CFIBounds(center=(32, 32), radius=32, hw=(64, 64), image=image)
    roi_dict = bounds.to_dict_all()
    transform, tensor = crop_fundus_from_roi(image, roi_dict, resize=32, apply_ce=False)
    assert transform is not None
    assert tensor.shape == (32, 32, 3)
