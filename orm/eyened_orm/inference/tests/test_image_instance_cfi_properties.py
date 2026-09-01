"""Tests for ImageInstance CFI attribute shorthand properties."""

from __future__ import annotations

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.tests.test_targets import _import_images


def test_cfi_properties_return_latest_version(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    image_id = image.ImageInstanceID

    roi_attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ROI",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    roi_old = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ROI", "Version": "0.9.0"},
        update_values={"Description": "roi"},
    )
    roi_new = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ROI", "Version": "1.0.0"},
        update_values={"Description": "roi"},
    )
    session.add(
        AttributeValue(
            AttributeID=roi_attr.AttributeID,
            ModelID=roi_old.ModelID,
            ImageInstanceID=image_id,
            ValueJSON={"center": [0, 0], "radius": 1, "lines": {}},
        )
    )
    session.add(
        AttributeValue(
            AttributeID=roi_attr.AttributeID,
            ModelID=roi_new.ModelID,
            ImageInstanceID=image_id,
            ValueJSON={"center": [5, 6], "radius": 7, "lines": {}},
        )
    )

    odfd_attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ODFD",
            "AttributeDataType": AttributeDataType.Float,
        },
    )
    odfd_model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ODFD", "Version": "1.0.0"},
        update_values={"Description": "odfd"},
    )
    session.add(
        AttributeValue(
            AttributeID=odfd_attr.AttributeID,
            ModelID=odfd_model.ModelID,
            ImageInstanceID=image_id,
            ValueFloat=0.42,
        )
    )
    session.commit()
    session.refresh(image)

    assert image.cfi_roi["center"] == [5, 6]
    assert image.cfi_odfd == 0.42
    assert image.odfd == 0.42


def test_cfi_properties_return_none_when_missing(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    assert image.cfi_roi is None
    assert image.cfi_keypoints is None
    assert image.cfi_odfd is None
    assert image.cfi_quality is None
