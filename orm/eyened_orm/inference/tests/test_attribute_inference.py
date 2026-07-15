"""Tests for attribute inference pipeline model registration."""

from __future__ import annotations

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.test_targets import _import_images
from eyened_orm.inference.cfi_odfd import CFI_ODFD
from eyened_orm.inference.model_versions import huggingface_artifact_version
import torch


def test_attributes_model_description_synced_on_pipeline_init(session):
    """get_or_create update_values keeps Model.Description in sync with pipeline code."""
    odfd_version = huggingface_artifact_version(CFI_ODFD.HF_ARTIFACT)
    existing = AttributesModel(
        ModelName="CFI_ODFD",
        Version=odfd_version,
        Description="old description",
    )
    session.add(existing)
    session.commit()

    CFI_ODFD(session, device=torch.device("cpu"), n_workers=1)

    session.refresh(existing)
    assert existing.Description == CFI_ODFD.model_description


def test_save_result_links_input_provenance(session):
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
    roi_av = AttributeValue(
        AttributeID=roi_attr.AttributeID,
        ModelID=roi_model.ModelID,
        ImageInstanceID=image.ImageInstanceID,
        ValueJSON={"center": [10, 10], "radius": 20, "lines": {}},
    )
    session.add(roi_av)
    session.commit()

    pipeline = CFI_ODFD(session, device=torch.device("cpu"), n_workers=1)
    pipeline._input_values_by_image = {image.ImageInstanceID: {"CFI_ROI": roi_av}}
    pipeline._save_result(image.ImageInstanceID, 42.0)
    session.flush()

    output_av = AttributeValue.by_column(
        session,
        ImageInstanceID=image.ImageInstanceID,
        AttributeID=pipeline.attr_definition.AttributeID,
        ModelID=pipeline.model.ModelID,
    )
    assert output_av is not None
    assert roi_av in output_av.InputValues
