"""Tests for ImageInstance.roi missing vs failed warnings."""

from __future__ import annotations

import logging

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.test_targets import _import_images


def test_roi_warns_when_cfi_roi_never_ran(session, caplog):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    with caplog.at_level(logging.WARNING, logger="eyened_orm.image_instance"):
        assert image.roi is None

    assert "model has not run" in caplog.text
    assert "computation failed" not in caplog.text


def test_roi_warns_when_cfi_roi_failed(session, caplog):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    roi_attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ROI",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    roi_model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ROI", "Version": "1.0"},
        update_values={"Description": "roi"},
    )
    failed_av = AttributeValue(
        AttributeID=roi_attr.AttributeID,
        ModelID=roi_model.ModelID,
        ImageInstanceID=image.ImageInstanceID,
        ValueJSON=None,
    )
    session.add(failed_av)
    session.commit()
    session.refresh(image)

    with caplog.at_level(logging.WARNING, logger="eyened_orm.image_instance"):
        assert image.roi is None

    assert "computation failed" in caplog.text
    assert "model has not run" not in caplog.text


def test_roi_returns_value_when_cfi_roi_succeeded(session, caplog):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    roi_attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ROI",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    roi_model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ROI", "Version": "1.0"},
        update_values={"Description": "roi"},
    )
    roi_json = {"center": [1, 2], "radius": 3, "lines": {}}
    session.add(
        AttributeValue(
            AttributeID=roi_attr.AttributeID,
            ModelID=roi_model.ModelID,
            ImageInstanceID=image.ImageInstanceID,
            ValueJSON=roi_json,
        )
    )
    session.commit()
    session.refresh(image)

    with caplog.at_level(logging.WARNING, logger="eyened_orm.image_instance"):
        roi = image.roi

    assert roi is not None
    assert roi["center"] == [1, 2]
    assert caplog.text == ""
