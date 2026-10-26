"""Tests for AttributeValue outcome detection (NULL-value failure shortcut)."""

from __future__ import annotations

from sqlalchemy import select

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.attribute_value_outcome import (
    AttributeValueOutcome,
    attribute_value_has_stored_value_sql,
    attribute_value_outcome,
    failure_update_values,
    has_stored_value,
    is_available_input,
)


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


def test_attribute_value_has_stored_value_sql_matches_python(session):
    _proj, images = _import_images(session, count=2)
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={"AttributeName": "CFI_ROI", "AttributeDataType": AttributeDataType.JSON},
    )
    model = AttributesModel.get_or_create(
        session, match_by={"ModelName": "CFI_ROI", "Version": "1.0"}
    )
    for image, value in zip(images, (None, {"center": [1, 2], "radius": 3})):
        session.add(
            AttributeValue(
                AttributeID=attr.AttributeID,
                ModelID=model.ModelID,
                ImageInstanceID=image.ImageInstanceID,
                ValueJSON=value,
            )
        )
    session.commit()

    succeeded = set(
        session.scalars(
            select(AttributeValue.ImageInstanceID)
            .where(attribute_value_has_stored_value_sql())
            .distinct()
        ).all()
    )
    assert succeeded == {images[1].ImageInstanceID}
