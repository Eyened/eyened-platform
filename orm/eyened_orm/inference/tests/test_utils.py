"""Tests for CFI inference image loading helpers."""

from __future__ import annotations

import numpy as np

from eyened_orm.inference.utils import as_uint8_rgb, preprocess_image


def test_as_uint8_rgb_from_grayscale():
    gray = np.array([[0, 128], [255, 64]], dtype=np.uint8)
    rgb = as_uint8_rgb(gray)
    assert rgb.shape == (2, 2, 3)
    assert rgb.dtype == np.uint8
    np.testing.assert_array_equal(rgb[:, :, 0], gray)


def test_preprocess_image_accepts_rgb_array():
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[16:48, 16:48] = 200
    transform, tensor = preprocess_image(image, resize=32, apply_ce=False)
    assert tensor.shape == (32, 32, 3)
    assert transform is not None
