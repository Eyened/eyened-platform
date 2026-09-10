"""ETDRS model processing warps native-space masks into image space."""

from __future__ import annotations

import numpy as np
import pytest

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
    Feature,
    ModelSegmentation,
    SegmentationModel,
)
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.reports.etdrs_model import ETDRSModelProcessor
from eyened_orm.segmentation import DataRepresentation, Datatype

SCALE2 = [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 1.0]]


def _seed_seg_model(session, name: str = "Drusen") -> SegmentationModel:
    feature = Feature.get_or_create(session, match_by={"FeatureName": name})
    return SegmentationModel.get_or_create(
        session,
        match_by={
            "FeatureID": feature.FeatureID,
            "ModelName": name,
            "Version": "1",
        },
    )


def _seed_keypoints(session, image_id: int, fovea_xy=(4.0, 4.0)) -> AttributeValue:
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_Keypoints",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_Keypoints", "Version": "1"},
        update_values={"Description": "kpts"},
    )
    av = AttributeValue(
        AttributeID=attr.AttributeID,
        ModelID=model.ModelID,
        ImageInstanceID=image_id,
        ValueJSON={"fovea_xy": list(fovea_xy), "disc_edge_xy": [6.0, 4.0]},
    )
    session.add(av)
    session.flush()
    return av


def _seed_odfd(session, image_id: int, value: float = 50.0) -> AttributeValue:
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ODFD",
            "AttributeDataType": AttributeDataType.Float,
        },
    )
    model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ODFD", "Version": "1"},
        update_values={"Description": "odfd"},
    )
    av = AttributeValue(
        AttributeID=attr.AttributeID,
        ModelID=model.ModelID,
        ImageInstanceID=image_id,
        ValueFloat=value,
    )
    session.add(av)
    session.flush()
    return av


def _prepare_image(session, *, height: int = 8, width: int = 8):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    image.Rows_y = height
    image.Columns_x = width
    image.NrOfFrames = 1
    return image


def _seed_model_seg(
    session,
    image,
    *,
    height: int,
    width: int,
    matrix=None,
) -> ModelSegmentation:
    ms = ModelSegmentation(
        ImageInstanceID=image.ImageInstanceID,
        ModelID=_seed_seg_model(session).ModelID,
        ZarrArrayIndex=0,
        Depth=1,
        Height=height,
        Width=width,
        SparseAxis=0,
        DataType=Datatype.R8,
        DataRepresentation=DataRepresentation.Probability,
        Threshold=0.5,
        ImageProjectionMatrix=matrix,
    )
    session.add(ms)
    session.flush()
    return ms


def _process(session, monkeypatch, ms, image, native):
    monkeypatch.setattr(ms, "read_data", lambda *a, **k: native)
    keypoints = _seed_keypoints(session, image.ImageInstanceID)
    odfd = _seed_odfd(session, image.ImageInstanceID)
    session.commit()
    return ETDRSModelProcessor(session).process(ms, keypoints, odfd)


def test_process_warps_projected_mask_to_image_space(session, monkeypatch):
    """Native 4×4 + scale-2 matrix must summarize at 8×8 image size."""
    image = _prepare_image(session)
    ms = _seed_model_seg(session, image, height=4, width=4, matrix=SCALE2)
    av = _process(
        session, monkeypatch, ms, image, np.full((1, 4, 4), 255, dtype=np.uint8)
    )

    assert av is not None
    assert av.ValueJSON
    assert av.ValueJSON.get("total_area", 0) > 0


def test_process_same_shape_mask_without_projection(session, monkeypatch):
    image = _prepare_image(session)
    ms = _seed_model_seg(session, image, height=8, width=8)
    av = _process(
        session, monkeypatch, ms, image, np.full((1, 8, 8), 255, dtype=np.uint8)
    )

    assert av is not None
    assert av.ValueJSON
    assert av.ValueJSON.get("total_area", 0) > 0


def test_process_raises_when_warped_mask_shape_mismatches(session, monkeypatch):
    image = _prepare_image(session)
    ms = _seed_model_seg(session, image, height=8, width=8)
    monkeypatch.setattr(
        ms, "read_data", lambda *a, **k: np.full((1, 8, 8), 255, dtype=np.uint8)
    )
    monkeypatch.setattr(
        ms, "warp_to_image", lambda *a, **k: np.ones((3, 3), dtype=np.uint8)
    )
    keypoints = _seed_keypoints(session, image.ImageInstanceID)
    odfd = _seed_odfd(session, image.ImageInstanceID)
    session.commit()

    with pytest.raises(ValueError, match="Shape mismatch"):
        ETDRSModelProcessor(session).process(ms, keypoints, odfd)


def test_process_returns_none_when_segmentation_has_no_data(session, monkeypatch):
    image = _prepare_image(session)
    ms = _seed_model_seg(session, image, height=8, width=8)
    av = _process(session, monkeypatch, ms, image, None)

    assert av is None
