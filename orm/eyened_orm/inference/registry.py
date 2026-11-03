"""Every model the platform can run, in run order (producers before consumers).

The slug is the CLI ``-m`` value, the API ``models`` value and the RQ queue
name. To add a model, write a :class:`~eyened_orm.inference.pipeline.Pipeline`
subclass and add one :class:`ModelSpec` line here.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from eyened_orm import Modality

if TYPE_CHECKING:
    from eyened_orm.inference.pipeline import Pipeline


@dataclass(frozen=True)
class ModelSpec:
    slug: str
    pipeline: str
    """``"module:Class"``; imported lazily so the registry needs no torch."""
    modalities: tuple[Modality, ...]
    batch_size: int = 8
    n_workers: int = 8
    supports_upscale: bool = False
    seconds_per_image: int | None = None
    """RQ job timeout per image (clamped to 10 min .. 24 h); ``None`` = queue default."""

    def load(self) -> type[Pipeline]:
        module, _, name = self.pipeline.partition(":")
        return getattr(importlib.import_module(module), name)

    def job_timeout(self, image_count: int) -> int | None:
        if self.seconds_per_image is None:
            return None
        return min(86400, max(600, max(1, image_count) * self.seconds_per_image))


_CFI = (Modality.ColorFundus,)
_PKG = "eyened_orm.inference"

MODELS: dict[str, ModelSpec] = {
    spec.slug: spec
    for spec in (
        ModelSpec("cfi-roi", f"{_PKG}.cfi_roi:CFI_ROI", _CFI),
        ModelSpec("cfi-keypoints", f"{_PKG}.cfi_keypoints:CFIKeypoints", _CFI, n_workers=4),
        ModelSpec("cfi-odfd", f"{_PKG}.cfi_odfd:CFI_ODFD", _CFI),
        ModelSpec("cfi-quality", f"{_PKG}.cfi_quality:CFI_Quality", _CFI),
        ModelSpec(
            "cfi-amd",
            f"{_PKG}.cfi_amd_segmentation:CFI_AMD",
            _CFI,
            n_workers=12,
            supports_upscale=True,
        ),
        ModelSpec(
            "cfi-drusen",
            f"{_PKG}.cfi_drusen_segmentation:CFI_Drusen",
            _CFI,
            batch_size=1,
            n_workers=0,
            supports_upscale=True,
        ),
        ModelSpec(
            "layer-segmentation",
            f"{_PKG}.layer_segmentation:LayerSegmentation",
            (Modality.OCT,),
            batch_size=1,
            n_workers=0,
            seconds_per_image=600,
        ),
    )
}

MODEL_SLUGS: tuple[str, ...] = tuple(MODELS)


def get_spec(slug: str) -> ModelSpec:
    try:
        return MODELS[slug]
    except KeyError:
        raise ValueError(
            f"Unknown model {slug!r}; choose from {', '.join(MODEL_SLUGS)}"
        ) from None
