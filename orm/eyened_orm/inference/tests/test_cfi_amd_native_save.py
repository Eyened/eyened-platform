"""Native CFI AMD segmentation storage (no upscale + image_projection_matrix)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")
import torch

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
    ModelSegmentation,
)
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.cfi_amd_segmentation import (
    CFI_AMD,
    image_projection_matrix_from_cfi_roi,
)


def _seed_cfi_roi(session, image_id: int, *, height: int = 128, width: int = 128):
    roi_attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ROI",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    roi_model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ROI", "Version": "1.0"},
        update_values={"Description": "roi"},
    )
    session.add(
        AttributeValue(
            AttributeID=roi_attr.AttributeID,
            ModelID=roi_model.ModelID,
            ImageInstanceID=image_id,
            ValueJSON={
                "center": [width / 2, height / 2],
                "radius": min(height, width) / 2,
                "lines": {},
                "hw": [height, width],
            },
        )
    )
    session.commit()


def _prepare_image(image, *, height: int = 128, width: int = 128) -> None:
    image.Rows_y = height
    image.Columns_x = width
    image.NrOfFrames = 1


def test_image_projection_matrix_from_cfi_roi_matches_cropping_inverse(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image)
    _seed_cfi_roi(session, image.ImageInstanceID)
    session.refresh(image)

    stored = image_projection_matrix_from_cfi_roi(image)
    expected = np.asarray(image.cropping_matrix_inverse, dtype=float)
    np.testing.assert_allclose(stored, expected)


def test_image_projection_matrix_from_cfi_roi_requires_bounds(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image)
    session.commit()

    with pytest.raises(ValueError, match="no CFI_ROI bounds"):
        image_projection_matrix_from_cfi_roi(image)


def test_save_result_stores_native_output_and_projection_matrix(session, monkeypatch):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=256, width=256)
    _seed_cfi_roi(session, image.ImageInstanceID, height=256, width=256)
    session.refresh(image)

    written = []

    def fake_write_data(self, data, axis=None, slice_index=None):
        written.append(np.asarray(data))
        return 0

    monkeypatch.setattr(ModelSegmentation, "write_data", fake_write_data)

    processor = CFI_AMD(
        session, device=torch.device("cpu"), undo_transform=False
    )
    native = np.full((32, 32), 0.8, dtype=np.float32)
    processor._save_result(image.ImageInstanceID, processor.models["drusen"], native)

    row = ModelSegmentation.by_column(
        session,
        ImageInstanceID=image.ImageInstanceID,
        ModelID=processor.models["drusen"].ModelID,
    )
    assert row.Height == 32
    assert row.Width == 32
    assert row.Depth == 1
    np.testing.assert_allclose(
        row.ImageProjectionMatrix,
        image.cropping_matrix_inverse,
    )
    assert len(written) == 1
    assert written[0].shape == (32, 32)
    assert written[0].dtype == np.uint8


def test_save_result_upscale_path_omits_projection_matrix(session, monkeypatch):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=64, width=64)
    session.commit()

    monkeypatch.setattr(ModelSegmentation, "write_data", lambda *a, **k: 0)

    processor = CFI_AMD(
        session, device=torch.device("cpu"), undo_transform=True
    )
    full = np.full((64, 64), 0.8, dtype=np.float32)
    processor._save_result(image.ImageInstanceID, processor.models["drusen"], full)

    row = ModelSegmentation.by_column(
        session,
        ImageInstanceID=image.ImageInstanceID,
        ModelID=processor.models["drusen"].ModelID,
    )
    assert row.Height == 64
    assert row.Width == 64
    assert row.ImageProjectionMatrix is None
