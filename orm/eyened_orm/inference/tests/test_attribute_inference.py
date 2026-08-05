"""Tests for attribute inference pipeline model registration."""

from __future__ import annotations

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
from eyened_orm.inference.cfi_odfd import CFI_ODFD
from eyened_orm.inference.model_versions import huggingface_artifact_version


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
    pipeline._input_data_by_image = {
        image.ImageInstanceID: {"CFI_ROI": roi_av.ValueJSON}
    }
    pipeline._input_av_ids_by_image = {
        image.ImageInstanceID: {"CFI_ROI": roi_av.AttributeValueID}
    }
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


def test_commit_pending_batch_replays_after_deadlock(session, monkeypatch):
    """Rollback must not drop siblings: retry re-applies the whole open batch."""
    from sqlalchemy.exc import OperationalError

    import eyened_orm.inference.attribute_inference as ai_mod
    from eyened_orm.inference.cfi_roi import CFI_ROI

    _proj, images = _import_images(session, count=3)
    pipeline = CFI_ROI(session, n_workers=1)
    session.commit()  # persist model/attr rows before we simulate a failed commit

    commit_calls = {"n": 0}
    real_commit = session.commit

    def flaky_commit():
        commit_calls["n"] += 1
        if commit_calls["n"] == 1:
            raise OperationalError(
                "statement",
                {},
                Exception(1213, "Deadlock found when trying to get lock"),
            )
        return real_commit()

    monkeypatch.setattr(session, "commit", flaky_commit)
    monkeypatch.setattr(ai_mod.time, "sleep", lambda _s: None)

    pending = [
        (images[0].ImageInstanceID, {"center": [1, 2], "radius": 3}),
        (images[1].ImageInstanceID, None),
        (images[2].ImageInstanceID, {"center": [4, 5], "radius": 6}),
    ]
    pipeline._commit_pending_batch(pending)

    assert pending == []
    assert commit_calls["n"] == 2

    rows = {
        av.ImageInstanceID: av
        for av in AttributeValue.by_columns(
            session,
            AttributeID=pipeline.attr_definition.AttributeID,
            ModelID=pipeline.model.ModelID,
            ImageInstanceID={im.ImageInstanceID for im in images},
        )
    }
    assert set(rows) == {im.ImageInstanceID for im in images}
    assert rows[images[0].ImageInstanceID].ValueJSON == {
        "center": [1, 2],
        "radius": 3,
    }
    assert rows[images[1].ImageInstanceID].ValueJSON is None
    assert rows[images[2].ImageInstanceID].ValueJSON == {
        "center": [4, 5],
        "radius": 6,
    }
