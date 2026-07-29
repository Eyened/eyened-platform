"""End-to-end tests for CFI_Quality input dependency resolution and provenance."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")
import torch

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.test_targets import _import_images
from eyened_orm.inference.cfi_quality import CFI_Quality
from eyened_orm.inference.model_inputs import CFI_ROI_INPUT, ModelInputSpec


def _seed_cfi_roi(
    session,
    image_id: int,
    *,
    roi_json: dict | None = None,
    model_version: str = "1.0",
) -> AttributeValue:
    roi_attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ROI",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    roi_model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ROI", "Version": model_version},
        update_values={"Description": "roi"},
    )
    roi_av = AttributeValue(
        AttributeID=roi_attr.AttributeID,
        ModelID=roi_model.ModelID,
        ImageInstanceID=image_id,
        ValueJSON=roi_json
        or {"center": [64, 64], "radius": 40, "lines": {}, "hw": [128, 128]},
    )
    session.add(roi_av)
    session.commit()
    return roi_av


def test_cfi_quality_declares_cfi_roi_dependency():
    """Step 1: pipeline declares CFI_ROI via ModelInputSpec (any registered version)."""
    assert CFI_Quality.required_inputs == (CFI_ROI_INPUT,)
    assert CFI_ROI_INPUT.attribute_name == "CFI_ROI"
    assert CFI_ROI_INPUT.model_name == "CFI_ROI"
    assert CFI_ROI_INPUT.min_version is None


def test_cfi_quality_registers_input_dependency_in_database(session):
    """Step 1 (persisted): init registers ModelInput row for CFI_ROI."""
    pipeline = CFI_Quality(session, device=torch.device("cpu"), n_workers=1)
    session.flush()

    model = AttributesModel.by_column(
        session, ModelName="CFI_Quality", Version=pipeline.model_version
    )
    assert model is not None
    assert len(model.ModelInputs) == 1
    assert model.ModelInputs[0].InputName == "CFI_ROI"


def test_filter_image_ids_skips_images_without_cfi_roi(session):
    """Step 2: generic resolution filters out images missing required inputs."""
    _proj, images = _import_images(session, count=1)
    image = images[0]

    pipeline = CFI_Quality(session, device=torch.device("cpu"), n_workers=1)
    filtered = pipeline.filter_image_ids([image.ImageInstanceID])

    assert filtered == set()


def test_filter_image_ids_overwrite_still_skips_missing_cfi_roi(session):
    """Overwrite re-runs existing output but not images missing required inputs."""
    _proj, images = _import_images(session, count=1)
    image = images[0]

    pipeline = CFI_Quality(session, device=torch.device("cpu"), n_workers=1)
    filtered = pipeline.filter_image_ids(
        [image.ImageInstanceID], overwrite=True
    )

    assert filtered == set()


def test_filter_image_ids_overwrite_includes_existing_output(session):
    """Overwrite includes images that already have output when inputs are ready."""
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _seed_cfi_roi(session, image.ImageInstanceID)

    pipeline = CFI_Quality(session, device=torch.device("cpu"), n_workers=1)
    pipeline._save_result(image.ImageInstanceID, 3.5)
    session.commit()

    assert pipeline.filter_image_ids([image.ImageInstanceID]) == set()
    assert pipeline.filter_image_ids(
        [image.ImageInstanceID], overwrite=True
    ) == {image.ImageInstanceID}


def test_filter_image_ids_includes_image_with_cfi_roi(session):
    """Step 2: image with stored CFI_ROI passes generic input filter."""
    _proj, images = _import_images(session, count=1)
    image = images[0]
    roi_av = _seed_cfi_roi(session, image.ImageInstanceID)

    pipeline = CFI_Quality(session, device=torch.device("cpu"), n_workers=1)
    filtered = pipeline.filter_image_ids([image.ImageInstanceID])

    assert filtered == {image.ImageInstanceID}
    assert pipeline._input_values_by_image[image.ImageInstanceID]["CFI_ROI"] == roi_av


def test_filter_image_ids_rejects_cfi_roi_below_min_version(session):
    """min_version must match AttributesModel.Version exactly; 0.9.0 != 1.0.0."""
    from eyened_orm.inference.model_inputs import resolve_input_attribute_value

    _proj, images = _import_images(session, count=1)
    image = images[0]
    _seed_cfi_roi(session, image.ImageInstanceID, model_version="0.9.0")

    resolved = resolve_input_attribute_value(
        session,
        image_id=image.ImageInstanceID,
        spec=ModelInputSpec(
            "CFI_ROI", "CFI_ROI", min_version="1.0.0"
        ),
    )
    assert resolved is None


def test_input_data_passed_in_worker_payload(session, monkeypatch):
    """Step 3: resolved DB value is extracted and attached to InferenceItem."""
    _proj, images = _import_images(session, count=1)
    image = images[0]
    roi_json = {"center": [10, 20], "radius": 30, "lines": {}, "hw": [128, 128]}
    _seed_cfi_roi(session, image.ImageInstanceID, roi_json=roi_json)

    pipeline = CFI_Quality(session, device=torch.device("cpu"), n_workers=1)
    pipeline._ensure_inputs_resolved([image.ImageInstanceID])

    input_data = pipeline._input_data_for_image(image.ImageInstanceID)
    assert input_data is not None
    assert input_data["CFI_ROI"] == roi_json

    fake_rgb = np.zeros((8, 8, 3), dtype=np.uint8)
    monkeypatch.setattr(pipeline, "_load_image_rgb", lambda _img: fake_rgb)

    items = pipeline._build_preprocess_items([image])
    _, inference_item = items[0]
    assert inference_item is not None
    assert inference_item.input_values == input_data
    assert inference_item.image_rgb is fake_rgb


def test_save_result_links_cfi_roi_provenance(session):
    """Step 4: output AttributeValue records CFI_ROI as input provenance."""
    _proj, images = _import_images(session, count=1)
    image = images[0]
    roi_av = _seed_cfi_roi(session, image.ImageInstanceID)

    pipeline = CFI_Quality(session, device=torch.device("cpu"), n_workers=1)
    pipeline._ensure_inputs_resolved([image.ImageInstanceID])
    pipeline._save_result(image.ImageInstanceID, 3.5)
    session.flush()

    output_av = AttributeValue.by_column(
        session,
        ImageInstanceID=image.ImageInstanceID,
        AttributeID=pipeline.attr_definition.AttributeID,
        ModelID=pipeline.model.ModelID,
    )
    assert output_av is not None
    assert output_av.ValueFloat == 3.5
    assert roi_av in output_av.InputValues
