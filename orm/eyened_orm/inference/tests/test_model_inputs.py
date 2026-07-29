"""Tests for model input resolution and registration."""

from __future__ import annotations

import pytest

pytest.importorskip("torch")
import torch

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributeValue,
)
from eyened_orm.commands.test_targets import _import_images
from eyened_orm.inference.model_inputs import (
    ModelInputSpec,
    attribute_value_data,
    resolve_input_attribute_value,
)
from eyened_orm.inference.cfi_odfd import CFI_ODFD


def test_resolve_input_attribute_value_picks_matching_version(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    attr = AttributeDefinition.get_or_create(
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
    av = AttributeValue(
        AttributeID=attr.AttributeID,
        ModelID=roi_model.ModelID,
        ImageInstanceID=image.ImageInstanceID,
        ValueJSON={"center": [1, 2], "radius": 3, "lines": {}},
    )
    session.add(av)
    session.commit()

    resolved = resolve_input_attribute_value(
        session,
        image_id=image.ImageInstanceID,
        spec=ModelInputSpec("CFI_ROI", "CFI_ROI", "1.0"),
    )
    assert resolved is not None
    assert resolved.AttributeValueID == av.AttributeValueID


def test_attribute_value_data_reads_columns_without_relationships():
    av = AttributeValue(ValueJSON={"center": [1, 2]})
    assert attribute_value_data(av) == {"center": [1, 2]}


def test_pipeline_registers_model_inputs_and_outputs(session):
    pipeline = CFI_ODFD(session, device=torch.device("cpu"), n_workers=1)
    session.flush()

    model = AttributesModel.by_column(
        session, ModelName="CFI_ODFD", Version=pipeline.model_version
    )
    assert model is not None
    assert any(
        out.AttributeName == "CFI_ODFD" for out in model.OutputAttributes
    )
    assert len(model.ModelInputs) == 1
    assert model.ModelInputs[0].InputName == "CFI_ROI"
