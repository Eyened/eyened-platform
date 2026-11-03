"""CFI drusen pipeline: which processor call each mode uses and the mask it returns."""

from __future__ import annotations

import numpy as np
import pytest

from eyened_orm.inference import cfi_drusen_segmentation
from eyened_orm.inference.cfi_drusen_segmentation import CFI_Drusen

MATRIX = [[1.0, 0.0, 2.0], [0.0, 1.0, 3.0], [0.0, 0.0, 1.0]]


class _FakeProcessor:
    def __init__(self, mask_shape=(8, 8)):
        self.calls = []
        self.mask_shape = mask_shape

    def process(self, image):
        self.calls.append("full")
        return np.full(image.shape[:2], 0.9, dtype=np.float32)

    def process_with_transform(self, image):
        self.calls.append("fov")
        return {"M": MATRIX}, np.full(self.mask_shape, 0.8, dtype=np.float32)


@pytest.fixture
def processor(monkeypatch):
    fake = _FakeProcessor()
    monkeypatch.setattr(cfi_drusen_segmentation, "_make_processor", lambda device: fake)
    return fake


def test_native_mode_returns_field_of_view_mask_and_transform(processor):
    result = CFI_Drusen().predict(np.zeros((32, 32, 3), dtype=np.uint8))

    assert processor.calls == ["fov"]
    assert result.masks["drusen"].shape == (8, 8)
    assert result.projection_matrix == MATRIX


def test_upscale_returns_mask_in_photo_space_without_matrix(processor):
    result = CFI_Drusen(upscale=True).predict(np.zeros((16, 20, 3), dtype=np.uint8))

    assert processor.calls == ["full"]
    assert result.masks["drusen"].shape == (16, 20)
    assert result.projection_matrix is None


@pytest.mark.parametrize(("shape", "ok"), [((1, 8, 8), True), ((2, 8, 8), False)])
def test_mask_must_reduce_to_2d(processor, shape, ok):
    processor.mask_shape = shape
    pipeline = CFI_Drusen()
    image = np.zeros((8, 8, 3), dtype=np.uint8)

    if ok:
        assert pipeline.predict(image).masks["drusen"].shape == (8, 8)
    else:
        with pytest.raises(ValueError, match="must be 2D"):
            pipeline.predict(image)
