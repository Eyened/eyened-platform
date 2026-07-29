"""Tests for AttributeValue outcome detection (NULL-value failure shortcut)."""

from __future__ import annotations

import pytest

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.test_targets import _import_images
from eyened_orm.inference.attribute_value_outcome import (
    AttributeValueOutcome,
    attribute_value_outcome,
    failure_update_values,
    has_stored_value,
    is_available_input,
)
from eyened_orm.inference.cfi_roi import CFI_ROI


def test_attribute_value_outcome_missing():
    assert attribute_value_outcome(None) == AttributeValueOutcome.MISSING


def test_attribute_value_outcome_succeeded_with_value():
    av = AttributeValue(ValueFloat=3.5)
    assert attribute_value_outcome(av) == AttributeValueOutcome.SUCCEEDED
    assert has_stored_value(av)


def test_attribute_value_outcome_failed_with_null_columns():
    av = AttributeValue(
        ValueJSON=None,
        ValueFloat=None,
        ValueInt=None,
        ValueText=None,
    )
    assert attribute_value_outcome(av) == AttributeValueOutcome.FAILED
    assert not has_stored_value(av)


def test_is_available_input_requires_stored_value():
    assert not is_available_input(AttributeValue(ValueJSON=None))
    assert is_available_input(AttributeValue(ValueJSON={"center": [1, 2]}))


def test_failure_update_values_clears_all_columns():
    assert failure_update_values() == {
        "ValueJSON": None,
        "ValueFloat": None,
        "ValueInt": None,
        "ValueText": None,
    }


def test_filter_image_ids_skips_succeeded_and_failed_rows(session):
    torch = pytest.importorskip("torch")
    from eyened_orm.inference.cfi_odfd import CFI_ODFD

    _proj, images = _import_images(session, count=2)
    image_ok, image_failed = images

    pipeline = CFI_ODFD(session, device=torch.device("cpu"), n_workers=1)

    pipeline._save_result(image_ok.ImageInstanceID, 1.0)
    pipeline._save_failure(image_failed.ImageInstanceID)
    session.commit()

    filtered = pipeline.filter_image_ids(
        [image_ok.ImageInstanceID, image_failed.ImageInstanceID]
    )
    assert filtered == set()


def test_filter_image_ids_includes_images_without_rows(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    pipeline = CFI_ROI(session, n_workers=1)
    filtered = pipeline.filter_image_ids([image.ImageInstanceID])

    assert filtered == {image.ImageInstanceID}


def test_save_failure_does_not_erase_existing_value(session):
    torch = pytest.importorskip("torch")
    from eyened_orm.inference.cfi_odfd import CFI_ODFD

    _proj, images = _import_images(session, count=1)
    image = images[0]

    pipeline = CFI_ODFD(session, device=torch.device("cpu"), n_workers=1)
    pipeline._save_result(image.ImageInstanceID, 1.0)
    session.flush()

    pipeline._save_failure(image.ImageInstanceID)
    session.flush()

    av = AttributeValue.by_column(
        session,
        ImageInstanceID=image.ImageInstanceID,
        AttributeID=pipeline.attr_definition.AttributeID,
        ModelID=pipeline.model.ModelID,
    )
    assert av is not None
    assert av.ValueFloat == 1.0
    assert attribute_value_outcome(av) == AttributeValueOutcome.SUCCEEDED


def test_save_failure_persists_null_value_row(session):
    torch = pytest.importorskip("torch")
    from eyened_orm.inference.cfi_odfd import CFI_ODFD

    _proj, images = _import_images(session, count=1)
    image = images[0]

    pipeline = CFI_ODFD(session, device=torch.device("cpu"), n_workers=1)
    pipeline._save_failure(image.ImageInstanceID)
    session.flush()

    av = AttributeValue.by_column(
        session,
        ImageInstanceID=image.ImageInstanceID,
        AttributeID=pipeline.attr_definition.AttributeID,
        ModelID=pipeline.model.ModelID,
    )
    assert av is not None
    assert attribute_value_outcome(av) == AttributeValueOutcome.FAILED


def test_resolve_input_excludes_failed_cfi_roi(session):
    torch = pytest.importorskip("torch")
    from eyened_orm.inference.cfi_quality import CFI_Quality

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
    session.add(
        AttributeValue(
            AttributeID=roi_attr.AttributeID,
            ModelID=roi_model.ModelID,
            ImageInstanceID=image.ImageInstanceID,
            ValueJSON=None,
        )
    )
    session.commit()

    pipeline = CFI_Quality(session, device=torch.device("cpu"), n_workers=1)
    filtered = pipeline.filter_image_ids([image.ImageInstanceID])

    assert filtered == set()
