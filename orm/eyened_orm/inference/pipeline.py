"""Base class every registered model implements (pure compute, no database).

A model declares its ``output`` (where results are stored), optional ``inputs``
(attribute values it consumes) and ``image_input`` (how pixels are decoded),
then overrides the stage hooks it needs:

- ``load()`` — load weights once, before the first batch
- ``preprocess(item)`` — runs in worker processes; return ``None`` to fail one image
- ``process_batch(preps)`` — runs in the parent on a list of preprocessed items
- ``postprocess(prep, out)`` — turn one batch output into the stored result

Persistence, skip modes and provenance are handled by
:func:`eyened_orm.inference.runner.run_model` using ``output``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import numpy as np

from eyened_orm.inference.multi_process_inference import BaseInferencePipeline

if TYPE_CHECKING:
    from eyened_orm import ImageInstance
    from eyened_orm.inference.model_inputs import ModelInputSpec
    from eyened_orm.inference.outputs import AttributeOutput, SegmentationOutput


@dataclass(frozen=True)
class InferenceItem:
    """Picklable worker payload: decoded pixels plus plain resolved input values."""

    image: np.ndarray | None
    input_values: dict[str, Any] | None = None


class Pipeline(BaseInferencePipeline):
    output: ClassVar[AttributeOutput | SegmentationOutput]
    inputs: tuple[ModelInputSpec, ...] = ()
    image_input: ClassVar[Literal["fundus_rgb", "volume"]] = "fundus_rgb"
    needs_torch: ClassVar[bool] = True

    def __init__(self, device: Any = None, *, upscale: bool = False) -> None:
        self.device = device
        self.upscale = upscale
        self._loaded = False

    def load(self) -> None:
        """Load model weights. Called once, lazily."""

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()
            self._loaded = True

    def load_image(self, image: ImageInstance) -> np.ndarray:
        if self.image_input == "volume":
            return image.pixel_array
        from eyened_orm.inference.utils import load_fundus_rgb

        return load_fundus_rgb(image)

    def predict(self, image: np.ndarray, input_values: dict[str, Any] | None = None) -> Any:
        """Run all stages on one image in this process (no database)."""
        self.ensure_loaded()
        prep = self.preprocess(InferenceItem(image, input_values))
        if prep is None:
            raise ValueError(f"{type(self).__name__}: preprocessing returned no result")
        (out,) = list(self.process_batch([prep]))
        return self.postprocess(prep, out)

    def forward(self, model: Any, prep_batch: list[tuple[Any, np.ndarray]]) -> np.ndarray:
        """Stack ``(transform, HWC image)`` preps, run ``model`` under no_grad, return numpy."""
        import torch

        x_np = np.stack([im.transpose(2, 0, 1) for _, im in prep_batch], axis=0)
        x = torch.from_numpy(x_np).to(device=self.device, dtype=torch.float32)
        with torch.no_grad():
            return model(x).detach().cpu().numpy()
