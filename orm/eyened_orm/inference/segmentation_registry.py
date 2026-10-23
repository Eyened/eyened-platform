"""Registered segmentation models (slug, modalities, CLI dispatch)."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from eyened_orm import Modality


@dataclass(frozen=True, slots=True)
class SegmentationSpec:
    slug: str
    modalities: tuple[Modality, ...]
    module: str
    supports_upscale: bool = False
    uses_batch_workers: bool = False


SEGMENTATION_REGISTRY: dict[str, SegmentationSpec] = {
    "cfi-amd": SegmentationSpec(
        "cfi-amd",
        (Modality.ColorFundus,),
        "eyened_orm.inference.cfi_amd_segmentation",
        supports_upscale=True,
        uses_batch_workers=True,
    ),
    "cfi-drusen": SegmentationSpec(
        "cfi-drusen",
        (Modality.ColorFundus,),
        "eyened_orm.inference.cfi_drusen_segmentation",
        supports_upscale=True,
        uses_batch_workers=True,
    ),
    "layer-segmentation": SegmentationSpec(
        "layer-segmentation",
        (Modality.OCT,),
        "eyened_orm.inference.layer_segmentation",
    ),
}

SEGMENTATION_MODEL_SLUGS: tuple[str, ...] = tuple(SEGMENTATION_REGISTRY.keys())

CFI_SEGMENTATION_MODEL_SLUGS: tuple[str, ...] = tuple(
    slug
    for slug, spec in SEGMENTATION_REGISTRY.items()
    if Modality.ColorFundus in spec.modalities and Modality.OCT not in spec.modalities
)

OCT_SEGMENTATION_MODEL_SLUGS: tuple[str, ...] = tuple(
    slug
    for slug, spec in SEGMENTATION_REGISTRY.items()
    if Modality.OCT in spec.modalities
)

SEGMENTATION_SLUG_MODALITIES: dict[str, tuple[Modality, ...]] = {
    slug: spec.modalities for slug, spec in SEGMENTATION_REGISTRY.items()
}


def run_registered_segmentation(
    spec: SegmentationSpec,
    session,
    image_ids,
    *,
    device: Any = None,
    batch_size: int = 8,
    n_workers: int = 12,
    overwrite: bool = False,
    upscale: bool = False,
) -> None:
    """Call ``run_for_image_ids`` for a registered slug with the right kwargs."""
    module = importlib.import_module(spec.module)
    run = module.run_for_image_ids
    kwargs: dict[str, Any] = {
        "session": session,
        "image_ids": image_ids,
        "device": device,
        "overwrite": overwrite,
    }
    if spec.uses_batch_workers:
        kwargs["batch_size"] = batch_size
        kwargs["n_workers"] = n_workers
    if spec.supports_upscale:
        kwargs["upscale"] = upscale
    run(**kwargs)
