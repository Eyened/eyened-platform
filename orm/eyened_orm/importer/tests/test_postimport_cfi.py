"""Local post-import CFI runs must not import torch for cfi-roi."""


def test_local_cfi_attribute_roi_does_not_resolve_torch_device(monkeypatch, session):
    from eyened_orm.importer.postimport import _local_cfi_attribute

    calls: list[dict] = []

    def fake_run(sess, image_ids, model_slug, **kwargs):
        calls.append({"slug": model_slug, "device": kwargs.get("device")})

    def boom(_device):
        raise AssertionError("cfi-roi must not resolve a torch device")

    monkeypatch.setattr(
        "eyened_orm.commands.model_processing.run_cfi_attribute_pipeline",
        fake_run,
    )
    monkeypatch.setattr(
        "eyened_orm.commands.model_processing._get_device",
        boom,
    )

    _local_cfi_attribute(session, [1], "cfi-roi", device="cuda:0")
    assert calls == [{"slug": "cfi-roi", "device": None}]
