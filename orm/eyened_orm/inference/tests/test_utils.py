"""Tests for CFI inference image loading helpers."""

from __future__ import annotations

import numpy as np

from eyened_orm.inference.utils import as_uint8_rgb


def test_as_uint8_rgb_from_grayscale():
    gray = np.array([[0, 128], [255, 64]], dtype=np.uint8)
    rgb = as_uint8_rgb(gray)
    assert rgb.shape == (2, 2, 3)
    assert rgb.dtype == np.uint8
    np.testing.assert_array_equal(rgb[:, :, 0], gray)

