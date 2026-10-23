"""Native CFI AMD projection matrix, derived from the CFI_ROI input."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.cfi_amd_segmentation import cfi_roi_projection_matrix

ROI = {"center": [64, 64], "radius": 64, "lines": {}, "hw": [128, 128]}


def test_projection_matrix_matches_image_cropping_inverse(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    image.Rows_y, image.Columns_x, image.NrOfFrames = 128, 128, 1
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={"AttributeName": "CFI_ROI", "AttributeDataType": AttributeDataType.JSON},
    )
    model = AttributesModel.get_or_create(
        session, match_by={"ModelName": "CFI_ROI", "Version": "1.0"}
    )
    session.add(
        AttributeValue(
            AttributeID=attr.AttributeID,
            ModelID=model.ModelID,
            ImageInstanceID=image.ImageInstanceID,
            ValueJSON=ROI,
        )
    )
    session.commit()
    session.refresh(image)

    np.testing.assert_allclose(
        cfi_roi_projection_matrix(ROI), np.asarray(image.cropping_matrix_inverse, dtype=float)
    )


def test_projection_matrix_requires_bounds():
    with pytest.raises(ValueError, match="No CFI_ROI bounds"):
        cfi_roi_projection_matrix(None)
