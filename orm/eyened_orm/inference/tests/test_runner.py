"""End-to-end ``run_model`` behaviour, driven by the fake models in ``fake_models``."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy.exc import OperationalError

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributeValue,
    Modality,
    ModelSegmentation,
)
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference import registry, runner
from eyened_orm.inference.outputs import AttributeSink
from eyened_orm.inference.registry import ModelSpec
from eyened_orm.inference.runner import run_model
from eyened_orm.inference.tests import fake_models
from eyened_orm.inference.tests.fake_models import MATRIX, FakeScore, FakeSegmentation

_FAKE = "eyened_orm.inference.tests.fake_models"
_CFI = (Modality.ColorFundus,)


@pytest.fixture(autouse=True)
def fake_registry(monkeypatch):
    for spec in (
        ModelSpec("fake-score", f"{_FAKE}:FakeScore", _CFI, batch_size=2, n_workers=0),
        ModelSpec("fake-score-v2", f"{_FAKE}:FakeScoreV2", _CFI, n_workers=0),
        ModelSpec("fake-seg", f"{_FAKE}:FakeSegmentation", _CFI, n_workers=0, supports_upscale=True),
    ):
        monkeypatch.setitem(registry.MODELS, spec.slug, spec)


@pytest.fixture
def written(monkeypatch):
    calls: list[np.ndarray] = []
    monkeypatch.setattr(
        ModelSegmentation,
        "write_data",
        lambda self, data, axis=None, slice_index=None: calls.append(np.asarray(data)) or 0,
    )
    return calls


def _cfi_images(session, count: int) -> list[int]:
    _proj, images = _import_images(session, count=count)
    for image in images:
        image.Modality = Modality.ColorFundus
        image.Rows_y, image.Columns_x, image.NrOfFrames = 4, 4, 1
    session.commit()
    return [image.ImageInstanceID for image in images]


def _seed_roi(
    session, image_id: int, radius: float = 5.0, *, failed: bool = False
) -> AttributeValue:
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={"AttributeName": "CFI_ROI", "AttributeDataType": AttributeDataType.JSON},
    )
    model = AttributesModel.get_or_create(
        session, match_by={"ModelName": "CFI_ROI", "Version": "1.0"}
    )
    av = AttributeValue(
        AttributeID=attr.AttributeID,
        ModelID=model.ModelID,
        ImageInstanceID=image_id,
        ValueJSON=None if failed else {"center": [2, 2], "radius": radius, "lines": {}},
    )
    session.add(av)
    session.commit()
    return av


def _scores(session, version: str = "1") -> dict[int, float | None]:
    model = AttributesModel.by_column(session, ModelName="Fake_Score", Version=version)
    return {
        av.ImageInstanceID: av.ValueFloat
        for av in AttributeValue.by_columns(session, ModelID=model.ModelID)
    }


# --- attribute output -------------------------------------------------------


def test_writes_values_and_links_input_provenance(session):
    ids = _cfi_images(session, 2)
    rois = {i: _seed_roi(session, i, radius=i) for i in ids}

    summary = run_model(session, "fake-score", ids)

    assert summary.processed == 2
    assert _scores(session) == {i: i * 10 + i for i in ids}
    model = AttributesModel.by_column(session, ModelName="Fake_Score", Version="1")
    for i in ids:
        av = AttributeValue.by_column(session, ImageInstanceID=i, ModelID=model.ModelID)
        assert av.InputValues == {rois[i]}
    assert [m.InputName for m in model.ModelInputs] == ["CFI_ROI"]


def test_images_missing_required_inputs_are_skipped(session):
    ids = _cfi_images(session, 3)
    _seed_roi(session, ids[0])
    _seed_roi(session, ids[2], failed=True)

    summary = run_model(session, "fake-score", ids)

    assert summary.skipped_missing_inputs == 2
    assert set(_scores(session)) == {ids[0]}


def test_other_modalities_are_ignored(session):
    _proj, images = _import_images(session, count=2)  # one CFI, one OCT
    for image in images:
        _seed_roi(session, image.ImageInstanceID)

    summary = run_model(session, "fake-score", [i.ImageInstanceID for i in images])

    assert summary.candidates == 1


def test_failure_is_recorded_without_erasing_an_earlier_success(session, monkeypatch):
    ids = _cfi_images(session, 2)
    for i in ids:
        _seed_roi(session, i)
    run_model(session, "fake-score", [ids[0]])

    monkeypatch.setattr(FakeScore, "fail_ids", frozenset(ids))
    summary = run_model(session, "fake-score", ids, mode="overwrite")

    assert summary.failed == ids
    scores = _scores(session)
    assert scores[ids[0]] == ids[0] * 10 + 5
    assert scores[ids[1]] is None  # failed row kept so re-runs skip it


# --- skip modes -------------------------------------------------------------


@pytest.fixture
def outcome_matrix(session, monkeypatch):
    """Five images with different prior outcomes for Fake_Score.

    old: succeeded with version 1 only; failed: failed with version 2;
    new: succeeded with version 2; none: never ran; retried: failed with
    version 1 then succeeded with version 2.
    """
    ids = dict(zip(("old", "failed", "new", "none", "retried"), _cfi_images(session, 5)))
    for i in ids.values():
        _seed_roi(session, i)
    monkeypatch.setattr(FakeScore, "fail_ids", frozenset({ids["retried"]}))
    run_model(session, "fake-score", [ids["old"], ids["retried"]])
    monkeypatch.setattr(FakeScore, "fail_ids", frozenset({ids["failed"]}))
    run_model(
        session, "fake-score-v2", [ids["failed"], ids["new"], ids["retried"]], mode="upgrade"
    )
    monkeypatch.setattr(FakeScore, "fail_ids", frozenset())
    return ids


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("default", {"none"}),
        ("upgrade", {"old", "none"}),
        ("failed", {"failed"}),
        ("overwrite", {"old", "failed", "new", "none", "retried"}),
    ],
)
def test_mode_selects_pending_images(session, outcome_matrix, mode, expected):
    summary = run_model(session, "fake-score-v2", outcome_matrix.values(), mode=mode)

    assert summary.pending == len(expected)
    assert summary.processed == len(expected)


def test_upgrade_writes_new_version_alongside_old(session, outcome_matrix):
    old = outcome_matrix["old"]
    run_model(session, "fake-score-v2", [old], mode="upgrade")

    assert _scores(session, "1")[old] == old * 10 + 5
    assert _scores(session, "2")[old] == old * 10 + 5


def test_unknown_mode_is_rejected(session):
    with pytest.raises(ValueError, match="Unknown mode"):
        run_model(session, "fake-score", [], mode="sometimes")


# --- segmentation output ----------------------------------------------------


def _segmentations(session, image_id: int) -> dict[str, ModelSegmentation]:
    rows = ModelSegmentation.by_columns(session, ImageInstanceID=image_id)
    return {row.Model.ModelName: row for row in rows}


def test_segmentation_stores_every_feature_with_projection_matrix(session, written):
    (image_id,) = _cfi_images(session, 1)

    run_model(session, "fake-seg", [image_id])

    rows = _segmentations(session, image_id)
    assert set(rows) == {"Fake A", "Fake B"}
    for row in rows.values():
        assert (row.Depth, row.Height, row.Width) == (1, 4, 4)
        assert row.ImageProjectionMatrix == MATRIX
    assert len(written) == 2
    assert written[0].dtype == np.uint8 and written[0][0, 0] == 204


def test_upscale_stores_masks_without_projection_matrix(session, written):
    (image_id,) = _cfi_images(session, 1)

    run_model(session, "fake-seg", [image_id], upscale=True)

    assert all(r.ImageProjectionMatrix is None for r in _segmentations(session, image_id).values())


def test_segmentation_is_rerun_until_every_feature_is_present(session, written):
    (image_id,) = _cfi_images(session, 1)
    run_model(session, "fake-seg", [image_id])
    session.delete(_segmentations(session, image_id)["Fake B"])
    session.commit()

    summary = run_model(session, "fake-seg", [image_id])

    assert summary.pending == 1
    assert set(_segmentations(session, image_id)) == {"Fake A", "Fake B"}
    assert len(written) == 3  # existing feature A is not rewritten

    assert run_model(session, "fake-seg", [image_id]).pending == 0


def test_masks_below_threshold_are_not_written(session, written, monkeypatch):
    (image_id,) = _cfi_images(session, 1)
    monkeypatch.setattr(FakeSegmentation, "value", 0.1)

    run_model(session, "fake-seg", [image_id])

    assert written == []
    assert len(_segmentations(session, image_id)) == 2


def test_overwrite_cannot_change_segmentation_dimensions(session, written, monkeypatch):
    (image_id,) = _cfi_images(session, 1)
    run_model(session, "fake-seg", [image_id])
    monkeypatch.setattr(FakeSegmentation, "shape", (8, 8))

    with pytest.raises(RuntimeError, match="1 image"):
        run_model(session, "fake-seg", [image_id], mode="overwrite")

    assert {r.Height for r in _segmentations(session, image_id).values()} == {4}


def test_failed_mode_is_rejected_for_segmentation(session):
    (image_id,) = _cfi_images(session, 1)
    with pytest.raises(ValueError, match="do not record failures"):
        run_model(session, "fake-seg", [image_id], mode="failed")


def test_unrecorded_failures_fail_the_run_after_saving_the_rest(session, written, monkeypatch):
    ids = _cfi_images(session, 2)
    monkeypatch.setattr(FakeSegmentation, "fail_ids", frozenset({ids[1]}))

    with pytest.raises(RuntimeError, match=str(ids[1])):
        run_model(session, "fake-seg", ids)

    assert len(_segmentations(session, ids[0])) == 2
    assert _segmentations(session, ids[1]) == {}


# --- runner mechanics -------------------------------------------------------


def test_worker_processes_give_the_same_results_as_in_process(session):
    ids = _cfi_images(session, 3)
    for i in ids:
        _seed_roi(session, i)

    run_model(session, "fake-score", ids, n_workers=0)
    in_process = _scores(session)
    run_model(session, "fake-score", ids, n_workers=2, mode="overwrite")

    assert _scores(session) == in_process


def test_commit_replays_the_whole_batch_after_a_deadlock(session, monkeypatch):
    ids = _cfi_images(session, 3)
    for i in ids:
        _seed_roi(session, i)
    real_commit, real_save = session.commit, AttributeSink.save
    state = {"saved": False, "raised": False}

    def tracking_save(self, *args, **kwargs):
        state["saved"] = True
        return real_save(self, *args, **kwargs)

    def flaky_commit():
        if state["saved"] and not state["raised"]:
            state["raised"] = True
            raise OperationalError("stmt", {}, Exception(1213, "Deadlock found"))
        return real_commit()

    monkeypatch.setattr(AttributeSink, "save", tracking_save)
    monkeypatch.setattr(session, "commit", flaky_commit)
    monkeypatch.setattr(runner.time, "sleep", lambda _s: None)

    summary = run_model(session, "fake-score", ids, commit_interval=3)

    assert state["raised"]
    assert summary.processed == 3
    assert set(_scores(session)) == set(ids)


def test_device_is_not_resolved_for_models_without_torch():
    assert runner.resolve_device(fake_models.FakeScore, "cuda:7") is None
