"""Fundus probability segmentation base (save, filter, run)."""

from __future__ import annotations

import numpy as np
import pytest

from eyened_orm import Feature, ModelSegmentation, SegmentationModel
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.fundus_probability_segmentation import (
    FundusProbabilitySegmentationPipeline,
)


class _StubPipeline(FundusProbabilitySegmentationPipeline):
    def __init__(self, session, *, mask: np.ndarray, matrix=None, overwrite=False):
        super().__init__(session, overwrite=overwrite)
        self._mask = mask
        self._matrix = matrix
        self.feature = Feature.get_or_create(
            session, match_by={"FeatureName": "StubFundus"}
        )
        self.model = SegmentationModel.get_or_create(
            session,
            match_by={
                "FeatureID": self.feature.FeatureID,
                "ModelName": "StubFundus",
                "Version": "1",
            },
            update_values={"Description": "test"},
        )

    def segmentation_models(self):
        return (self.model,)

    def _predict_for_image(self, rgb):
        yield self.model, self._mask, self._matrix


def _prepare_image(image, *, height: int, width: int) -> None:
    image.Rows_y = height
    image.Columns_x = width
    image.NrOfFrames = 1


def test_save_probability_mask_skips_below_threshold(session, monkeypatch):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=8, width=8)
    session.commit()

    written = []
    monkeypatch.setattr(
        ModelSegmentation,
        "write_data",
        lambda self, data, axis=None, slice_index=None: written.append(np.asarray(data)),
    )
    pipeline = _StubPipeline(
        session, mask=np.full((4, 4), 0.1, dtype=np.float32)
    )
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda _image: np.zeros((8, 8, 3), dtype=np.uint8),
    )
    pipeline.run([image.ImageInstanceID])
    assert written == []


def test_save_probability_mask_rejects_dimension_change(session, monkeypatch):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=64, width=64)
    session.commit()

    monkeypatch.setattr(ModelSegmentation, "write_data", lambda *a, **k: 0)
    pipeline = _StubPipeline(
        session,
        mask=np.full((64, 64), 0.8, dtype=np.float32),
        overwrite=True,
    )
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda _image: np.zeros((64, 64, 3), dtype=np.uint8),
    )
    pipeline.run([image.ImageInstanceID])

    with pytest.raises(ValueError, match="Cannot modify Height"):
        pipeline._save_probability_mask(
            image.ImageInstanceID,
            pipeline.model,
            np.full((32, 32), 0.9, dtype=np.float32),
            None,
        )


def test_filter_image_ids_waits_until_all_models_present(session, monkeypatch):
    _proj, images = _import_images(session, count=2)
    a, b = images[0], images[1]
    _prepare_image(a, height=8, width=8)
    _prepare_image(b, height=8, width=8)
    session.commit()

    monkeypatch.setattr(ModelSegmentation, "write_data", lambda *a, **k: 0)
    pipeline = _StubPipeline(
        session, mask=np.full((8, 8), 0.8, dtype=np.float32)
    )
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda _image: np.zeros((8, 8, 3), dtype=np.uint8),
    )
    assert pipeline.filter_image_ids([a.ImageInstanceID, b.ImageInstanceID]) == {
        a.ImageInstanceID,
        b.ImageInstanceID,
    }

    pipeline.run([a.ImageInstanceID])

    assert pipeline.filter_image_ids([a.ImageInstanceID, b.ImageInstanceID]) == {
        b.ImageInstanceID,
    }
