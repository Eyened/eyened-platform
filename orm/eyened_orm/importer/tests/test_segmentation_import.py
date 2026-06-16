from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest
from sqlalchemy import select

from eyened_orm import ImageInstance, Segmentation
from eyened_orm.importer import ImportRow, plan_image_import
from eyened_orm.importer.importer_dtos import SegmentationImport
from eyened_orm.importer.segmentation_import import (
    plan_segmentation_import,
    segmentation_import_to_row,
)
from eyened_orm.segmentation_storage import get_zarr_storage_manager, read_segmentation_data


@pytest.fixture
def zarr_storage_root(monkeypatch, tmp_path):
    monkeypatch.setenv("EYENED_STORAGE_ROOT", str(tmp_path))
    get_zarr_storage_manager.cache_clear()
    yield tmp_path
    get_zarr_storage_manager.cache_clear()


def _import_one_image(session) -> ImageInstance:
    defaults = {
        "project_external": "Y",
        "manufacturer": "m",
        "manufacturer_model_name": "mm",
        "device_description": "d",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    plan_image_import(
        session,
        [
            ImportRow(
                project_name="seg-proj",
                patient_identifier="pat-1",
                study_date=datetime.now().date(),
                series_anonymous_identity=1,
                storage_backend_key="sb",
                object_key="img.png",
                modality="ColorFundus",
                laterality="L",
                height=4,
                width=6,
                depth=1,
            )
        ],
        defaults=defaults,
    ).apply()
    session.commit()
    img = session.scalar(select(ImageInstance))
    assert img is not None
    return img


def test_segmentation_import_to_row(session):
    img = _import_one_image(session)
    mask = np.zeros((1, 4, 6), dtype=np.uint8)
    row = segmentation_import_to_row(
        img.ImageInstanceID,
        SegmentationImport(
            data=mask,
            feature_name="Vessel",
            creator_name="alice",
        ),
    )
    assert row.image_instance_id == img.ImageInstanceID
    assert row.height == 4 and row.width == 6 and row.depth == 1


def test_plan_segmentation_import(session, zarr_storage_root):
    img = _import_one_image(session)
    mask = np.ones((1, 4, 6), dtype=np.uint8)

    plan_segmentation_import(
        session,
        img.ImageInstanceID,
        [
            SegmentationImport(
                data=mask,
                feature_name="Vessel",
                creator_name="alice",
            )
        ],
        commit=True,
    )

    seg = session.scalar(select(Segmentation))
    assert seg is not None
    assert np.array_equal(read_segmentation_data(seg), mask)
