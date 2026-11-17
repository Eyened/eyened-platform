"""``eorm run-model`` maps flags onto ``run_model`` and reports per-model failures."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from click.testing import CliRunner

from eyened_orm.commands.model_processing import run_model_command, run_models
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.outputs import UnsupportedMode
from eyened_orm.inference.registry import MODEL_SLUGS


class _Calls(list):
    behaviour: dict[str, Exception]


@pytest.fixture
def calls(monkeypatch, SessionLocal):
    """Record ``run_model`` calls; ``behaviour[slug]`` may raise for that model."""
    recorded = _Calls()
    recorded.behaviour = behaviour = {}

    class FakeDatabase:
        @contextmanager
        def get_session(self):
            with SessionLocal() as session:
                yield session

    def fake_run_model(session, slug, image_ids, **kwargs):
        recorded.append({"slug": slug, "image_ids": set(image_ids), **kwargs})
        if slug in behaviour:
            raise behaviour[slug]

    monkeypatch.setattr(
        "eyened_orm.commands.model_processing.get_database", lambda **_: FakeDatabase()
    )
    monkeypatch.setattr("eyened_orm.inference.runner.run_model", fake_run_model)
    return recorded


def _invoke(command, *args):
    return CliRunner().invoke(command, list(args))


def test_flags_map_onto_run_model(session, calls):
    _proj, images = _import_images(session, count=2)
    ids = {i.ImageInstanceID for i in images}

    result = _invoke(
        run_model_command,
        "-m", "cfi-amd",
        "-m", "cfi-roi",
        "--upgrade",
        "--upscale",
        "-d", "cpu",
        "-b", "4",
        "-w", "0",
        "--commit-interval", "7",
    )

    assert result.exit_code == 0, result.output
    assert [c["slug"] for c in calls] == ["cfi-amd", "cfi-roi"]
    assert calls[0] == {
        "slug": "cfi-amd",
        "image_ids": ids,
        "device": "cpu",
        "mode": "upgrade",
        "upscale": True,
        "batch_size": 4,
        "n_workers": 0,
        "commit_interval": 7,
    }


def test_no_model_runs_every_registered_model_in_order(session, calls):
    _import_images(session, count=1)

    result = _invoke(run_model_command)

    assert result.exit_code == 0, result.output
    assert [c["slug"] for c in calls] == list(MODEL_SLUGS)
    assert all(c["mode"] == "default" for c in calls)


def test_mode_flags_are_mutually_exclusive(session, calls):
    _import_images(session, count=1)
    result = _invoke(run_model_command, "--failed", "--overwrite")

    assert result.exit_code == 2
    assert "at most one" in result.output
    assert calls == []


def test_unsupported_mode_is_a_usage_error_for_an_explicit_model(session, calls):
    _import_images(session, count=1)
    calls.behaviour["cfi-amd"] = UnsupportedMode("no failure rows")

    result = _invoke(run_model_command, "-m", "cfi-amd", "--failed")

    assert result.exit_code == 2
    assert "cfi-amd: no failure rows" in result.output


def test_unsupported_mode_skips_that_model_when_running_all(session, calls):
    _import_images(session, count=1)
    calls.behaviour["cfi-amd"] = UnsupportedMode("no failure rows")

    result = _invoke(run_model_command, "--failed")

    assert result.exit_code == 0, result.output
    assert "Skipping cfi-amd" in result.output
    assert [c["slug"] for c in calls] == list(MODEL_SLUGS)


def test_a_failing_model_does_not_stop_the_next_but_fails_the_command(session, calls):
    _import_images(session, count=1)
    calls.behaviour["cfi-roi"] = RuntimeError("cfi-roi: 2 image(s) failed")

    result = _invoke(run_model_command, "-m", "cfi-roi", "-m", "cfi-odfd")

    assert result.exit_code == 1
    assert "cfi-roi: 2 image(s) failed" in result.output
    assert [c["slug"] for c in calls] == ["cfi-roi", "cfi-odfd"]


def test_run_models_is_a_deprecated_alias(session, calls):
    _import_images(session, count=1)
    result = _invoke(run_models, "-m", "cfi-roi")

    assert result.exit_code == 0, result.output
    assert "deprecated" in result.output
    assert [c["slug"] for c in calls] == ["cfi-roi"]
