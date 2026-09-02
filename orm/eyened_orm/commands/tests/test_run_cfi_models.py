"""Click CLI tests for run-cfi-models."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from click.testing import CliRunner

from eyened_orm.commands.model_processing import (
    CFI_ATTRIBUTE_MODEL_SLUGS,
    run_cfi_models,
)
from eyened_orm.commands.tests.test_targets import _import_images


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def pipeline_calls(monkeypatch, SessionLocal):
    """Record run_cfi_attribute_pipeline invocations with a test SQLite session."""
    calls: list[dict] = []

    class FakeDatabase:
        @contextmanager
        def get_session(self):
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

    def fake_get_database(**_kwargs):
        return FakeDatabase()

    def fake_run(session, image_ids, model_slug, **kwargs):
        calls.append(
            {
                "slug": model_slug,
                "image_ids": set(image_ids),
                "overwrite": kwargs.get("overwrite"),
                "upgrade": kwargs.get("upgrade"),
                "failed": kwargs.get("failed"),
                "device": kwargs.get("device"),
                "batch_size": kwargs.get("batch_size"),
                "n_workers": kwargs.get("n_workers"),
                "commit_interval": kwargs.get("commit_interval"),
            }
        )

    monkeypatch.setattr(
        "eyened_orm.commands.model_processing.get_database",
        fake_get_database,
    )
    monkeypatch.setattr(
        "eyened_orm.commands.model_processing.run_cfi_attribute_pipeline",
        fake_run,
    )
    monkeypatch.setattr(
        "eyened_orm.commands.model_processing._get_device",
        lambda _device: "mock-device",
    )

    return calls


def test_run_cfi_models_default_targets_all_images(
    session, cli_runner, pipeline_calls
):
    _proj, images = _import_images(session)
    session.commit()

    result = cli_runner.invoke(run_cfi_models, [])

    assert result.exit_code == 0, result.output
    assert len(pipeline_calls) == len(CFI_ATTRIBUTE_MODEL_SLUGS)
    assert [call["slug"] for call in pipeline_calls] == list(
        CFI_ATTRIBUTE_MODEL_SLUGS
    )
    # Default target is ColorFundus only (not every modality in the DB).
    expected_ids = {
        im.ImageInstanceID for im in images if im.Modality.name == "ColorFundus"
    }
    for call in pipeline_calls:
        assert call["image_ids"] == expected_ids
        assert call["overwrite"] is False
        assert call["upgrade"] is False
        assert call["failed"] is False


def test_run_cfi_models_single_model(cli_runner, pipeline_calls, session):
    _proj, images = _import_images(session, count=1)
    session.commit()

    result = cli_runner.invoke(run_cfi_models, ["-m", "cfi-quality"])

    assert result.exit_code == 0, result.output
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["slug"] == "cfi-quality"
    assert pipeline_calls[0]["image_ids"] == {images[0].ImageInstanceID}


def test_run_cfi_models_project_narrows_target(cli_runner, pipeline_calls, session):
    proj_a, images_a = _import_images(session, project_name="proj-a", count=1)
    _import_images(session, project_name="proj-b", count=1)
    session.commit()

    result = cli_runner.invoke(
        run_cfi_models, ["--project", str(proj_a.ProjectID)]
    )

    assert result.exit_code == 0, result.output
    assert len(pipeline_calls) == len(CFI_ATTRIBUTE_MODEL_SLUGS)
    expected_ids = {images_a[0].ImageInstanceID}
    for call in pipeline_calls:
        assert call["image_ids"] == expected_ids


def test_run_cfi_models_path_narrows_target(
    cli_runner, pipeline_calls, session, tmp_path
):
    _proj, images = _import_images(session, count=2)
    path = tmp_path / "ids.txt"
    path.write_text(f"{images[0].ImageInstanceID}\n")
    session.commit()

    result = cli_runner.invoke(run_cfi_models, ["--path", str(path)])

    assert result.exit_code == 0, result.output
    expected_ids = {images[0].ImageInstanceID}
    for call in pipeline_calls:
        assert call["image_ids"] == expected_ids


def test_run_cfi_models_modality_filter(cli_runner, pipeline_calls, session):
    _proj, images = _import_images(session)
    cfi = next(im for im in images if im.Modality.name == "ColorFundus")
    session.commit()

    result = cli_runner.invoke(run_cfi_models, ["--modality", "ColorFundus"])

    assert result.exit_code == 0, result.output
    for call in pipeline_calls:
        assert call["image_ids"] == {cfi.ImageInstanceID}


def test_run_cfi_models_slug_order_runs_cfi_roi_first(
    cli_runner, pipeline_calls, session
):
    _proj, _images = _import_images(session, count=1)
    session.commit()

    result = cli_runner.invoke(run_cfi_models, [])

    assert result.exit_code == 0, result.output
    assert pipeline_calls[0]["slug"] == "cfi-roi"
    assert [call["slug"] for call in pipeline_calls] == [
        "cfi-roi",
        "cfi-keypoints",
        "cfi-odfd",
        "cfi-quality",
    ]


@pytest.mark.parametrize(
    "flag,expected",
    [
        ("--upgrade", {"upgrade": True, "failed": False, "overwrite": False}),
        ("--failed", {"upgrade": False, "failed": True, "overwrite": False}),
        ("--overwrite", {"upgrade": False, "failed": False, "overwrite": True}),
    ],
)
def test_run_cfi_models_passes_mode_flags(
    cli_runner, pipeline_calls, session, flag, expected
):
    _proj, _images = _import_images(session, count=1)
    session.commit()

    result = cli_runner.invoke(run_cfi_models, ["-m", "cfi-roi", flag])

    assert result.exit_code == 0, result.output
    assert len(pipeline_calls) == 1
    call = pipeline_calls[0]
    assert call["upgrade"] is expected["upgrade"]
    assert call["failed"] is expected["failed"]
    assert call["overwrite"] is expected["overwrite"]


def test_run_cfi_models_passes_processing_options(
    cli_runner, pipeline_calls, session
):
    _proj, _images = _import_images(session, count=1)
    session.commit()

    result = cli_runner.invoke(
        run_cfi_models,
        [
            "-m",
            "cfi-keypoints",
            "-d",
            "cpu",
            "-b",
            "4",
            "-w",
            "2",
            "--commit-interval",
            "50",
        ],
    )

    assert result.exit_code == 0, result.output
    call = pipeline_calls[0]
    assert call["device"] == "mock-device"
    assert call["batch_size"] == 4
    assert call["n_workers"] == 2
    assert call["commit_interval"] == 50


def test_run_cfi_models_cfi_roi_does_not_resolve_torch_device(
    cli_runner, pipeline_calls, monkeypatch, session
):
    """cfi-roi uses fundusprep/OpenCV. Resolving a torch device breaks the server image."""

    def boom(_device):
        raise AssertionError("cfi-roi must not resolve a torch device")

    monkeypatch.setattr(
        "eyened_orm.commands.model_processing._get_device",
        boom,
    )
    _import_images(session, count=1)
    session.commit()

    result = cli_runner.invoke(run_cfi_models, ["-m", "cfi-roi"])

    assert result.exit_code == 0, result.output
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["slug"] == "cfi-roi"
    assert pipeline_calls[0]["device"] is None


def test_run_cfi_models_only_torch_slugs_get_a_device(
    cli_runner, pipeline_calls, session
):
    _import_images(session, count=1)
    session.commit()

    result = cli_runner.invoke(run_cfi_models, [])

    assert result.exit_code == 0, result.output
    by_slug = {call["slug"]: call["device"] for call in pipeline_calls}
    assert by_slug["cfi-roi"] is None
    for slug in ("cfi-keypoints", "cfi-odfd", "cfi-quality"):
        assert by_slug[slug] == "mock-device"


def test_get_device_missing_torch_points_at_inference_worker(monkeypatch):
    import builtins

    from eyened_orm.commands.model_processing import _get_device

    real_import = builtins.__import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("No module named 'torch'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)

    with pytest.raises(RuntimeError, match="worker/docker-compose.inference.yml"):
        _get_device(None)


def test_run_cfi_attribute_pipeline_filters_before_chunking(session, monkeypatch, capsys):
    from eyened_orm.commands import model_processing
    from eyened_orm.commands.model_processing import run_cfi_attribute_pipeline
    from eyened_orm.inference.cfi_roi import CFI_ROI

    _proj, images = _import_images(session, count=3)
    done_a, done_b, pending = images

    pipeline_probe = CFI_ROI(session, n_workers=1)
    pipeline_probe._save_result(done_a.ImageInstanceID, {"center": [1, 2], "radius": 3})
    pipeline_probe._save_failure(done_b.ImageInstanceID)
    session.commit()

    run_calls: list[set[int]] = []

    def fake_run(self, image_ids, commit_interval=100):
        run_calls.append(set(image_ids))

    monkeypatch.setattr(CFI_ROI, "run", fake_run)
    monkeypatch.setattr(
        model_processing,
        "_filter_supported_modalities",
        lambda session, ids, _modalities: set(ids),
    )

    run_cfi_attribute_pipeline(
        session,
        {im.ImageInstanceID for im in images},
        "cfi-roi",
        n_workers=1,
    )

    assert run_calls == [{pending.ImageInstanceID}]
    out = capsys.readouterr().out
    assert "3 candidates → 1 pending" in out
    assert "2 existing" in out
