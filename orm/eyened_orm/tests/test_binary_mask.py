"""Thresholding stored segmentation arrays to boolean masks."""

from __future__ import annotations

import numpy as np
import pytest

from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.tests.test_segmentation_warp import _make_2d_seg


def test_data_to_binary_mask_binary_and_dual_bit(session):
    seg = _make_2d_seg(session, seg_hw=(2, 2), image_hw=(2, 2))
    data = np.array([[0, 3], [1, 0]], dtype=np.uint8)

    np.testing.assert_array_equal(
        seg.data_to_binary_mask(data), [[False, True], [True, False]]
    )

    seg.DataRepresentation = DataRepresentation.DualBitMask
    np.testing.assert_array_equal(
        seg.data_to_binary_mask(data), [[False, True], [True, False]]
    )


def test_data_to_binary_mask_probability_float32(session):
    seg = _make_2d_seg(session, seg_hw=(2, 2), image_hw=(2, 2))
    seg.DataRepresentation = DataRepresentation.Probability
    seg.DataType = Datatype.R32F
    seg.Threshold = 0.5
    data = np.array([[0.1, 0.9], [0.5, 0.51]], dtype=np.float32)

    np.testing.assert_array_equal(
        seg.data_to_binary_mask(data), [[False, True], [False, True]]
    )


def test_data_to_binary_mask_rejects_multiclass(session):
    seg = _make_2d_seg(session, seg_hw=(2, 2), image_hw=(2, 2))
    seg.DataRepresentation = DataRepresentation.MultiClass

    with pytest.raises(ValueError, match="not supported for binary masks"):
        seg.data_to_binary_mask(np.ones((2, 2), dtype=np.uint8))


def test_binary_mask_thresholds_read_data(session, monkeypatch):
    seg = _make_2d_seg(session, seg_hw=(2, 2), image_hw=(2, 2))
    monkeypatch.setattr(
        seg,
        "read_data",
        lambda *a, **k: np.array([[0, 1], [0, 0]], dtype=np.uint8),
    )

    np.testing.assert_array_equal(seg.binary_mask, [[False, True], [False, False]])


def test_binary_mask_returns_none_when_unread(session, monkeypatch):
    seg = _make_2d_seg(session, seg_hw=(2, 2), image_hw=(2, 2))
    monkeypatch.setattr(seg, "read_data", lambda *a, **k: None)

    assert seg.binary_mask is None
