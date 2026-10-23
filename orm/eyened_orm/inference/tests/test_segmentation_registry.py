"""Segmentation model registry and dispatch."""

from __future__ import annotations

import importlib

from eyened_orm import Modality
from eyened_orm.inference.segmentation_registry import (
    CFI_SEGMENTATION_MODEL_SLUGS,
    OCT_SEGMENTATION_MODEL_SLUGS,
    SEGMENTATION_REGISTRY,
    SEGMENTATION_MODEL_SLUGS,
    SEGMENTATION_SLUG_MODALITIES,
    run_registered_segmentation,
)


def test_registry_covers_expected_slugs():
    assert set(SEGMENTATION_MODEL_SLUGS) == {
        "cfi-amd",
        "cfi-drusen",
        "layer-segmentation",
    }
    assert set(CFI_SEGMENTATION_MODEL_SLUGS) == {"cfi-amd", "cfi-drusen"}
    assert OCT_SEGMENTATION_MODEL_SLUGS == ("layer-segmentation",)
    assert SEGMENTATION_SLUG_MODALITIES["cfi-drusen"] == (Modality.ColorFundus,)


def test_each_spec_imports_run_for_image_ids():
    for slug, spec in SEGMENTATION_REGISTRY.items():
        module = importlib.import_module(spec.module)
        assert hasattr(module, "run_for_image_ids"), slug


def test_run_registered_passes_cfi_kwargs(monkeypatch):
    spec = SEGMENTATION_REGISTRY["cfi-amd"]
    seen: list[dict] = []
    mod = importlib.import_module(spec.module)
    monkeypatch.setattr(mod, "run_for_image_ids", lambda **kwargs: seen.append(kwargs))

    session = object()
    run_registered_segmentation(
        spec,
        session,
        [1, 2],
        device="cpu",
        batch_size=4,
        n_workers=2,
        overwrite=True,
        upscale=True,
    )
    assert seen == [
        {
            "session": session,
            "image_ids": [1, 2],
            "device": "cpu",
            "batch_size": 4,
            "n_workers": 2,
            "overwrite": True,
            "upscale": True,
        }
    ]


def test_run_registered_omits_upscale_for_layer(monkeypatch):
    spec = SEGMENTATION_REGISTRY["layer-segmentation"]
    seen: list[dict] = []
    mod = importlib.import_module(spec.module)
    monkeypatch.setattr(mod, "run_for_image_ids", lambda **kwargs: seen.append(kwargs))

    session = object()
    run_registered_segmentation(
        spec,
        session,
        [9],
        device="cpu",
        batch_size=8,
        n_workers=12,
        overwrite=False,
        upscale=True,
    )
    assert seen == [
        {
            "session": session,
            "image_ids": [9],
            "device": "cpu",
            "overwrite": False,
        }
    ]
