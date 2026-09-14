"""RQ CFI job entrypoint must not import torch for cfi-roi (slim worker image)."""

from __future__ import annotations

from contextlib import contextmanager


def test_run_cfi_model_for_image_ids_roi_does_not_resolve_torch_device(monkeypatch):
    from server.utils.tasks import run_cfi_model_for_image_ids

    calls: list[dict] = []

    class FakeDatabase:
        @contextmanager
        def get_session(self):
            yield object()

    def fake_run(session, image_ids, model, **kwargs):
        calls.append(
            {
                "image_ids": list(image_ids),
                "model": model,
                "device": kwargs.get("device"),
            }
        )

    def boom(_device):
        raise AssertionError("cfi-roi must not resolve a torch device")

    monkeypatch.setattr("eyened_orm.Database", FakeDatabase)
    monkeypatch.setattr(
        "eyened_orm.commands.model_processing.run_cfi_attribute_pipeline",
        fake_run,
    )
    monkeypatch.setattr(
        "eyened_orm.commands.model_processing._get_device",
        boom,
    )

    assert run_cfi_model_for_image_ids([11, 12], "cfi-roi") is True
    assert calls == [{"image_ids": [11, 12], "model": "cfi-roi", "device": None}]
