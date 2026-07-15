"""Tests for CFI model version migration, --upgrade filtering, and HF version pickup."""

from __future__ import annotations

import torch

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.test_targets import _import_images
from eyened_orm.inference.cfi_keypoints import CFIKeypoints
from eyened_orm.inference.migrate_model_versions import (
    migrate_attributes_model_version,
    migrate_cfi_attributes_model_versions,
)
from eyened_orm.inference.model_inputs import select_attribute_value
from eyened_orm.inference.model_versions import huggingface_pipeline_version


def _seed_keypoints_value(
    session,
    image_id: int,
    *,
    model_version: str,
    value_json: dict | None = None,
) -> AttributeValue:
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_Keypoints",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_Keypoints", "Version": model_version},
        update_values={"Description": f"keypoints {model_version}"},
    )
    av = AttributeValue(
        AttributeID=attr.AttributeID,
        ModelID=model.ModelID,
        ImageInstanceID=image_id,
        ValueJSON=value_json
        or {"fovea_xy": [1.0, 2.0], "disc_edge_xy": [3.0, 4.0]},
    )
    session.add(av)
    session.commit()
    return av


def _seed_cfi_roi(session, image_id: int, *, model_version: str = "1.0") -> None:
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
    session.add(
        AttributeValue(
            AttributeID=roi_attr.AttributeID,
            ModelID=roi_model.ModelID,
            ImageInstanceID=image_id,
            ValueJSON={
                "center": [64, 64],
                "radius": 40,
                "lines": {},
                "hw": [128, 128],
            },
        )
    )
    session.commit()


def test_migrate_renames_legacy_version_in_place(session):
    legacy_version = "july24"
    target_version = huggingface_pipeline_version(*CFIKeypoints.HF_ARTIFACTS)

    legacy_model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_Keypoints", "Version": legacy_version},
        update_values={"Description": "legacy"},
    )
    legacy_id = legacy_model.ModelID
    session.commit()

    stats = migrate_attributes_model_version(
        session,
        model_name="CFI_Keypoints",
        target_version=target_version,
    )
    session.commit()

    assert stats == "updated"
    updated = AttributesModel.by_id(session, legacy_id)
    assert updated is not None
    assert updated.Version == target_version
    assert (
        AttributesModel.by_column(
            session, ModelName="CFI_Keypoints", Version=legacy_version
        )
        is None
    )


def test_migrate_noop_when_target_version_already_exists(session):
    legacy_version = "july24"
    target_version = huggingface_pipeline_version(*CFIKeypoints.HF_ARTIFACTS)

    AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_Keypoints", "Version": legacy_version},
        update_values={"Description": "legacy"},
    )
    AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_Keypoints", "Version": target_version},
        update_values={"Description": "canonical"},
    )
    session.commit()

    status = migrate_attributes_model_version(
        session,
        model_name="CFI_Keypoints",
        target_version=target_version,
    )
    session.commit()

    assert status == "error"
    assert (
        AttributesModel.by_column(
            session, ModelName="CFI_Keypoints", Version=legacy_version
        )
        is not None
    )


def test_migrate_is_idempotent(session):
    target_version = huggingface_pipeline_version(*CFIKeypoints.HF_ARTIFACTS)
    AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_Keypoints", "Version": target_version},
        update_values={"Description": "canonical"},
    )
    session.commit()

    first = migrate_cfi_attributes_model_versions(session)
    session.commit()
    second = migrate_cfi_attributes_model_versions(session)
    session.commit()

    assert first["CFI_Keypoints"] == "skipped"
    assert second["CFI_Keypoints"] == "skipped"


def test_default_filter_includes_image_with_no_attribute_value(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi(session, image.ImageInstanceID)

    pipeline = CFIKeypoints(session, device=torch.device("cpu"), n_workers=1)
    filtered = pipeline.filter_image_ids([image.ImageInstanceID])

    assert filtered == {image.ImageInstanceID}


def test_default_filter_skips_when_any_version_has_output(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi(session, image.ImageInstanceID)
    _seed_keypoints_value(session, image.ImageInstanceID, model_version="july24")

    pipeline = CFIKeypoints(session, device=torch.device("cpu"), n_workers=1)
    filtered = pipeline.filter_image_ids([image.ImageInstanceID])

    assert filtered == set()


def test_upgrade_filter_includes_image_when_only_older_version_has_output(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi(session, image.ImageInstanceID)
    _seed_keypoints_value(session, image.ImageInstanceID, model_version="july24")

    pipeline = CFIKeypoints(session, device=torch.device("cpu"), n_workers=1)
    filtered = pipeline.filter_image_ids([image.ImageInstanceID], upgrade=True)

    assert filtered == {image.ImageInstanceID}


def test_upgrade_filter_skips_when_current_version_already_has_output(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi(session, image.ImageInstanceID)
    pipeline = CFIKeypoints(session, device=torch.device("cpu"), n_workers=1)
    pipeline._save_result(
        image.ImageInstanceID,
        {"fovea_xy": [1.0, 2.0], "disc_edge_xy": [3.0, 4.0]},
    )
    session.commit()

    filtered = pipeline.filter_image_ids([image.ImageInstanceID], upgrade=True)
    assert filtered == set()


def test_upgrade_writes_new_version_alongside_old_without_overwriting(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi(session, image.ImageInstanceID)
    old_version = (
        "Eyened/vascx/discedge/discedge_july23+Eyened/vascx/fovea/fovea_july23"
    )
    old_av = _seed_keypoints_value(
        session,
        image.ImageInstanceID,
        model_version=old_version,
        value_json={"fovea_xy": [1.0, 1.0], "disc_edge_xy": [2.0, 2.0]},
    )

    pipeline = CFIKeypoints(session, device=torch.device("cpu"), n_workers=1)
    from eyened_orm.inference.model_versions import version_sort_key

    assert version_sort_key(pipeline.model_version) > version_sort_key(old_version)
    assert pipeline.filter_image_ids([image.ImageInstanceID], upgrade=True) == {
        image.ImageInstanceID
    }

    pipeline._save_result(
        image.ImageInstanceID,
        {"fovea_xy": [9.0, 9.0], "disc_edge_xy": [8.0, 8.0]},
    )
    session.commit()
    session.refresh(image)

    session.refresh(old_av)
    assert old_av.ValueJSON == {"fovea_xy": [1.0, 1.0], "disc_edge_xy": [2.0, 2.0]}

    keypoint_rows = [
        av
        for av in image.AttributeValues
        if av.AttributeDefinition.AttributeName == "CFI_Keypoints"
        and av.ValueJSON is not None
    ]
    assert len(keypoint_rows) == 2

    selected = select_attribute_value(
        image.AttributeValues,
        attribute_name="CFI_Keypoints",
        producing_model_name="CFI_Keypoints",
    )
    assert selected is not None
    assert selected.ModelID == pipeline.model.ModelID
    assert selected.ValueJSON["fovea_xy"] == [9.0, 9.0]


def test_newer_hf_pipeline_version_registers_and_wins_lookup(session, monkeypatch):
    old_artifacts = CFIKeypoints.HF_ARTIFACTS
    new_artifacts = (
        "Eyened/vascx:fovea/fovea_july25.pt",
        "Eyened/vascx:discedge/discedge_july25.pt",
    )
    monkeypatch.setattr(CFIKeypoints, "HF_ARTIFACTS", new_artifacts)

    _proj, images = _import_images(session, count=1)
    image = images[0]

    old_version = huggingface_pipeline_version(*old_artifacts)
    new_version = huggingface_pipeline_version(*new_artifacts)
    from eyened_orm.inference.model_versions import version_sort_key

    assert version_sort_key(new_version) > version_sort_key(old_version)

    _seed_keypoints_value(
        session,
        image.ImageInstanceID,
        model_version=old_version,
        value_json={"fovea_xy": [1.0, 1.0], "disc_edge_xy": [2.0, 2.0]},
    )
    _seed_keypoints_value(
        session,
        image.ImageInstanceID,
        model_version=new_version,
        value_json={"fovea_xy": [9.0, 9.0], "disc_edge_xy": [8.0, 8.0]},
    )
    session.refresh(image)

    pipeline = CFIKeypoints(session, device=torch.device("cpu"), n_workers=1)
    assert pipeline.model_version == new_version
    assert (
        AttributesModel.by_column(
            session, ModelName="CFI_Keypoints", Version=new_version
        )
        is not None
    )

    selected = select_attribute_value(
        image.AttributeValues, attribute_name="CFI_Keypoints"
    )
    assert selected is not None
    assert selected.ValueJSON["fovea_xy"] == [9.0, 9.0]
