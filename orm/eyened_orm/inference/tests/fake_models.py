"""Tiny numpy models used to exercise the runner end to end.

``image[0, 0, 0]`` carries the ImageInstanceID so a model can fail chosen images.
"""

from __future__ import annotations

import numpy as np

from eyened_orm import AttributeDataType
from eyened_orm.inference.model_inputs import CFI_ROI_INPUT
from eyened_orm.inference.outputs import (
    AttributeOutput,
    SegFeature,
    SegmentationOutput,
    SegmentationResult,
)
from eyened_orm.inference.pipeline import Pipeline

MATRIX = [[1.0, 0.0, 2.0], [0.0, 1.0, 3.0], [0.0, 0.0, 1.0]]


class _FakeBase(Pipeline):
    needs_torch = False
    fail_ids: frozenset[int] = frozenset()

    def load_image(self, image):
        return np.full((4, 4, 3), image.ImageInstanceID, dtype=np.uint8)

    def preprocess(self, item):
        if int(item.image[0, 0, 0]) in self.fail_ids:
            return None
        return item


class FakeScore(_FakeBase):
    """Stores ``image id * 10 + ROI radius`` as a Float attribute."""

    output = AttributeOutput(
        model_name="Fake_Score",
        attribute_name="Fake_Score",
        data_type=AttributeDataType.Float,
        version="1",
        description="fake score",
    )
    inputs = (CFI_ROI_INPUT,)

    def postprocess(self, prep, out):
        return float(out.image[0, 0, 0]) * 10 + out.input_values["CFI_ROI"]["radius"]


class FakeScoreV2(FakeScore):
    output = AttributeOutput(
        model_name="Fake_Score",
        attribute_name="Fake_Score",
        data_type=AttributeDataType.Float,
        version="2",
    )


class FakeSegmentation(_FakeBase):
    """Two probability maps; native mode keeps a projection matrix."""

    output = SegmentationOutput(
        features=(
            SegFeature("a", "Fake feature A", "Fake A", "1"),
            SegFeature("b", "Fake feature B", "Fake B", "1"),
        )
    )
    value = 0.8
    shape = (4, 4)

    def postprocess(self, prep, out):
        mask = np.full(self.shape, self.value, dtype=np.float32)
        return SegmentationResult(
            {"a": mask, "b": mask},
            projection_matrix=None if self.upscale else MATRIX,
        )
