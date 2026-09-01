"""Click CLI tests for run-segmentation."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

pytest.importorskip("torch")
from click.testing import CliRunner

from eyened_orm.commands.model_processing import run_segmentation
from eyened_orm.commands.tests.test_targets import _import_images


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def segmentation_calls(monkeypatch, SessionLocal):
    """Record run_for_image_ids invocations with a test SQLite session."""
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

    def fake_cfi_amd_run(session, image_ids, **kwargs):
        calls.append(
            {
                "slug": "cfi-amd",
                "image_ids": set(image_ids),
                "overwrite": kwargs.get("overwrite"),
                "upscale": kwargs.get("upscale"),
                "batch_size": kwargs.get("batch_size"),
                "n_workers": kwargs.get("n_workers"),
            }
        )

    def fake_layer_run(session, image_ids, **kwargs):
        calls.append(
            {
                "slug": "layer-segmentation",
                "image_ids": set(image_ids),
                "overwrite": kwargs.get("overwrite"),
            }
        )

    monkeypatch.setattr(
        "eyened_orm.commands.model_processing.get_database",
        fake_get_database,
    )
    monkeypatch.setattr(
        "eyened_orm.commands.model_processing._get_device",
        lambda _device: "mock-device",
    )
    monkeypatch.setattr(
        "eyened_orm.inference.cfi_amd_segmentation.run_for_image_ids",
        fake_cfi_amd_run,
    )
    monkeypatch.setattr(
        "eyened_orm.inference.layer_segmentation.run_for_image_ids",
        fake_layer_run,
    )

    return calls


def test_run_segmentation_cfi_amd_defaults_to_no_upscale(
    session, cli_runner, segmentation_calls
):
    _proj, images = _import_images(session, count=1)
    cfi = next(im for im in images if im.Modality.name == "ColorFundus")
    session.commit()

    result = cli_runner.invoke(
        run_segmentation,
        ["-m", "cfi-amd", "--image-ids", str(cfi.ImageInstanceID)],
    )

    assert result.exit_code == 0, result.output
    assert len(segmentation_calls) == 1
    call = segmentation_calls[0]
    assert call["slug"] == "cfi-amd"
    assert call["upscale"] is False
    assert call["overwrite"] is False
    assert call["image_ids"] == {cfi.ImageInstanceID}


def test_run_segmentation_cfi_amd_upscale_flag(
    session, cli_runner, segmentation_calls
):
    _proj, images = _import_images(session, count=1)
    cfi = next(im for im in images if im.Modality.name == "ColorFundus")
    session.commit()

    result = cli_runner.invoke(
        run_segmentation,
        ["-m", "cfi-amd", "--image-ids", str(cfi.ImageInstanceID), "--upscale"],
    )

    assert result.exit_code == 0, result.output
    assert segmentation_calls[0]["upscale"] is True
