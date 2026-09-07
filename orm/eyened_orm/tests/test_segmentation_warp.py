"""Warp 2D segmentation data back to ImageInstance space."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pytest
from rtnls_fundusprep.transformation import Interpolation, ProjectiveTransform

from eyened_orm import Segmentation
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.utils.factories import (
    make_creator,
    make_device,
    make_feature,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)

SCALE2 = [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 1.0]]


def _make_2d_seg(
    session,
    *,
    seg_hw: tuple[int, int] = (4, 4),
    image_hw: tuple[int, int] = (8, 8),
    matrix=None,
    depth: int = 1,
) -> Segmentation:
    project = make_project(session, "warp")
    patient = make_patient(session, project, "warp-pat")
    study = make_study(session, patient, date(2024, 1, 1))
    series = make_series(session, study)
    device = make_device(session, "warp")
    backend = make_storage_backend(session, "warp")
    image = make_image(session, series, device, backend, "warp-img")
    image.Rows_y = image_hw[0]
    image.Columns_x = image_hw[1]
    image.NrOfFrames = depth if depth > 1 else 1
    session.flush()
    feature = make_feature(session, "warp-feat")
    creator = make_creator(session, "warp-creator")
    h, w = seg_hw
    seg = Segmentation(
        ImageInstanceID=image.ImageInstanceID,
        FeatureID=feature.FeatureID,
        CreatorID=creator.CreatorID,
        DataType=Datatype.R8UI,
        DataRepresentation=DataRepresentation.Binary,
        Depth=depth,
        Height=h,
        Width=w,
        SparseAxis=0,
        ImageProjectionMatrix=matrix,
        DateInserted=datetime(2024, 1, 1),
    )
    session.add(seg)
    session.flush()
    return seg


def test_warp_to_image_matches_projective_transform(session):
    """Scale-2 matrix warps a 4×4 mask onto a non-square image the same way as the snippet."""
    image_hw = (6, 10)
    seg = _make_2d_seg(session, image_hw=image_hw, matrix=SCALE2)
    data = np.arange(16, dtype=np.uint8).reshape(4, 4)

    expected = ProjectiveTransform(
        np.asarray(SCALE2, dtype=float),
        in_size=data.shape[:2],
        out_size=image_hw,
    ).warp(data, image_hw, mode=Interpolation.NEAREST)

    result = seg.warp_to_image(data)

    np.testing.assert_array_equal(result, expected)
    assert result.shape == image_hw


def test_warp_to_image_reads_and_squeezes_stored_volume(session, monkeypatch):
    """read_data() is (D, H, W); depth-1 volumes are squeezed before warping."""
    seg = _make_2d_seg(session, matrix=SCALE2)
    volume = np.arange(16, dtype=np.uint8).reshape(1, 4, 4)
    monkeypatch.setattr(seg, "read_data", lambda *a, **k: volume)

    image_hw = (8, 8)
    expected = ProjectiveTransform(
        np.asarray(SCALE2, dtype=float),
        in_size=(4, 4),
        out_size=image_hw,
    ).warp(volume[0], image_hw, mode=Interpolation.NEAREST)

    np.testing.assert_array_equal(seg.warp_to_image(), expected)


def test_warp_to_image_without_matrix_returns_2d_data(session):
    """No ImageProjectionMatrix means the mask already lives in image space."""
    seg = _make_2d_seg(session, seg_hw=(8, 8), image_hw=(8, 8), matrix=None)
    data = np.arange(64, dtype=np.uint8).reshape(8, 8)

    result = seg.warp_to_image(data)
    np.testing.assert_array_equal(result, data)
    assert result is not data
    result[0, 0] = 255
    assert data[0, 0] != 255


def test_warp_to_image_without_matrix_copies_squeezed_volume(session):
    """Squeezing (1, H, W) must not return a live view of storage."""
    seg = _make_2d_seg(session, seg_hw=(8, 8), image_hw=(8, 8), matrix=None)
    volume = np.arange(64, dtype=np.uint8).reshape(1, 8, 8)

    result = seg.warp_to_image(volume)
    np.testing.assert_array_equal(result, volume[0])
    result[0, 0] = 255
    assert volume[0, 0, 0] != 255


def test_warp_to_image_rejects_3d_segmentation(session):
    """is_2d guard fires even when the caller already passed a 2D plane."""
    seg = _make_2d_seg(
        session, seg_hw=(4, 4), image_hw=(4, 4), matrix=None, depth=4
    )
    data = np.ones((4, 4), dtype=np.uint8)

    with pytest.raises(ValueError, match="only supported for 2D segmentations"):
        seg.warp_to_image(data)


def test_warp_to_image_rejects_missing_image_size(session):
    seg = _make_2d_seg(session, matrix=SCALE2)
    seg.ImageInstance.Rows_y = None
    data = np.ones((4, 4), dtype=np.uint8)

    with pytest.raises(ValueError, match="missing Rows_y or Columns_x"):
        seg.warp_to_image(data)


def test_warp_to_image_rejects_height_singleton_volume(session):
    seg = _make_2d_seg(session, matrix=SCALE2)
    data = np.ones((4, 1, 4), dtype=np.uint8)

    with pytest.raises(ValueError, match=r"\(1, H, W\)"):
        seg.warp_to_image(data)


def test_warp_to_image_nearest_is_default_for_integer_masks(session):
    seg = _make_2d_seg(session, matrix=SCALE2)
    data = np.zeros((4, 4), dtype=np.uint8)
    data[1, 2] = 7

    result = seg.warp_to_image(data)
    nearest = ProjectiveTransform(
        np.asarray(SCALE2, dtype=float),
        in_size=(4, 4),
        out_size=(8, 8),
    ).warp(data, (8, 8), mode=Interpolation.NEAREST)

    np.testing.assert_array_equal(result, nearest)
    assert result[2, 4] == 7


def test_warp_to_image_probability_defaults_to_bilinear(session):
    seg = _make_2d_seg(session, matrix=SCALE2)
    seg.DataRepresentation = DataRepresentation.Probability
    data = np.zeros((4, 4), dtype=np.float32)
    data[1, 2] = 1.0

    result = seg.warp_to_image(data)
    bilinear = ProjectiveTransform(
        np.asarray(SCALE2, dtype=float),
        in_size=(4, 4),
        out_size=(8, 8),
    ).warp(data, (8, 8), mode=Interpolation.BILINEAR)

    np.testing.assert_allclose(result, bilinear)


def test_warp_to_image_uint32_nearest_preserves_bits(session):
    """R32UI has no OpenCV type; an int32 view under NEAREST keeps high bits."""
    seg = _make_2d_seg(session, matrix=SCALE2)
    seg.DataType = Datatype.R32UI
    data = np.zeros((4, 4), dtype=np.uint32)
    data[1, 2] = 1 << 17

    result = seg.warp_to_image(data)

    assert result.dtype == np.uint32
    assert result.shape == (8, 8)
    assert result[2, 4] == 1 << 17


def test_warp_to_image_rejects_uint32_bilinear(session):
    seg = _make_2d_seg(session, matrix=SCALE2)
    data = np.ones((4, 4), dtype=np.uint32)

    with pytest.raises(ValueError, match="nearest-neighbor"):
        seg.warp_to_image(data, mode=Interpolation.BILINEAR)
