"""CFI drusen segmentation via the bundled ``cfi_drusen`` processor."""

from __future__ import annotations

import numpy as np

from eyened_orm.inference.outputs import SegFeature, SegmentationOutput, SegmentationResult
from eyened_orm.inference.pipeline import Pipeline


def _make_processor(device):
    """Load the five bundled folds onto ``device``."""
    from cfi_drusen import Processor

    return Processor(device)


class CFI_Drusen(Pipeline):
    """Drusen probabilities for color fundus photos.

    Native mode stores the 1024×1024 field of view and the transform back to
    the photo; ``upscale`` stores the mask in the original photo.
    The processor scores one photo at a time, in the parent process.
    """

    output = SegmentationOutput(
        features=(
            SegFeature("drusen", "Drusen", "Drusen", "4", "https://github.com/Eyened/amd-features"),
        )
    )

    def load(self) -> None:
        self.processor = _make_processor(self.device)

    def process_batch(self, items):
        for item in items:
            if self.upscale:
                yield self.processor.process(item.image), None
            else:
                transform, mask = self.processor.process_with_transform(item.image)
                yield mask, np.asarray(transform["M"], dtype=float).tolist()

    def postprocess(self, item, out) -> SegmentationResult:
        mask, matrix = out
        mask = np.asarray(mask, dtype=np.float32)
        if mask.ndim == 3 and 1 in mask.shape:
            mask = np.squeeze(mask)
        if mask.ndim != 2:
            raise ValueError(f"Drusen mask must be 2D, got shape {mask.shape}")
        return SegmentationResult({"drusen": mask}, projection_matrix=matrix)
