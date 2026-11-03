"""Tests for model input resolution."""

from __future__ import annotations

import pytest

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributeValue,
)
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.model_inputs import (
    ModelInputSpec,
    attribute_value_data,
    resolve_input_attribute_value,
)


def _seed_roi(session, image_id: int, version: str) -> AttributeValue:
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ROI",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    roi_model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ROI", "Version": version},
        update_values={"Description": "roi"},
    )
    av = AttributeValue(
        AttributeID=attr.AttributeID,
        ModelID=roi_model.ModelID,
        ImageInstanceID=image_id,
        ValueJSON={"center": [1, 2], "radius": 3, "lines": {}},
    )
    session.add(av)
    session.commit()
    return av


@pytest.mark.parametrize(
    ("stored", "required", "found"),
    [("1.0", "1.0", True), ("0.9.0", "1.0.0", False)],
)
def test_resolve_input_attribute_value_matches_min_version(
    session, stored, required, found
):
    _proj, images = _import_images(session, count=1)
    image_id = images[0].ImageInstanceID
    av = _seed_roi(session, image_id, stored)

    resolved = resolve_input_attribute_value(
        session,
        image_id=image_id,
        spec=ModelInputSpec("CFI_ROI", "CFI_ROI", min_version=required),
    )

    assert (resolved is not None and resolved.AttributeValueID == av.AttributeValueID) is found


def test_attribute_value_data_reads_columns_without_relationships():
    av = AttributeValue(ValueJSON={"center": [1, 2]})
    assert attribute_value_data(av) == {"center": [1, 2]}
