"""Tests for image dimension validation and repair."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from eyened_orm import AuditLog, ImageInstance
from eyened_orm.commands.repair_image_dimensions import (
    TRUSTED_PATH,
    repair_image_dimensions_for_ids,
)
from eyened_orm.image_dimensions import (
    ImageDimensionMismatchError,
    apply_dimensions,
    assert_dimensions_match,
    blocking_dependents,
    dimensions_compatible,
    dimensions_from_array,
    effective_n_frames,
)
from eyened_orm.utils.factories import (
    make_creator,
    make_device,
    make_feature,
    make_image,
    make_patient,
    make_project,
    make_segmentation,
    make_series,
    make_storage_backend,
    make_study,
)
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401


@pytest.fixture
def image_graph(session):
    backend = make_storage_backend(session)
    project = make_project(session, "dim-proj")
    patient = make_patient(session, project, "P1")
    study = make_study(session, patient, datetime(2024, 1, 1).date())
    series = make_series(session, study)
    device = make_device(session, "d1")
    return session, series, device, backend


def test_dimensions_from_array_layouts():
    assert dimensions_from_array(np.zeros((10, 20))).shape_dhw == (1, 10, 20)
    assert dimensions_from_array(np.zeros((10, 20, 3))).shape_dhw == (1, 10, 20)
    assert dimensions_from_array(np.zeros((5, 10, 20))).shape_dhw == (5, 10, 20)


def test_none_frames_compatible_with_one():
    from eyened_orm.image_dimensions import ImageDimensions

    db = ImageDimensions(n_frames=1, rows_y=10, columns_x=20)
    arr = ImageDimensions(n_frames=None, rows_y=10, columns_x=20)
    assert dimensions_compatible(db, arr) == []
    assert effective_n_frames(None) == 1


def test_assert_raises_on_mismatch_without_mutating(image_graph):
    session, series, device, backend = image_graph
    image = make_image(session, series, device, backend, "img-mismatch")
    image.Rows_y = 10
    image.Columns_x = 20
    session.flush()
    array = np.zeros((8, 9, 3), dtype=np.uint8)
    before = (image.Rows_y, image.Columns_x, image.NrOfFrames)
    with pytest.raises(ImageDimensionMismatchError, match="Rows_y"):
        assert_dimensions_match(image, array)
    assert (image.Rows_y, image.Columns_x, image.NrOfFrames) == before


def test_assert_allows_unset_db_fields(image_graph):
    session, series, device, backend = image_graph
    image = make_image(session, series, device, backend, "img-unset")
    image.Rows_y = None
    image.Columns_x = None
    image.NrOfFrames = None
    session.flush()
    assert_dimensions_match(image, np.zeros((8, 9), dtype=np.uint8))
    assert image.Rows_y is None


def test_blocking_dependents(image_graph):
    session, series, device, backend = image_graph
    image = make_image(session, series, device, backend, "img-block")
    assert blocking_dependents(image) == []
    image.CFROI = {"hw": [4, 4]}
    assert "CFROI" in blocking_dependents(image)
    image.CFROI = None
    image.CFKeypoints = {"fovea_xy": [1, 2]}
    assert "CFKeypoints" in blocking_dependents(image)
    image.CFKeypoints = None
    creator = make_creator(session, "c1")
    feature = make_feature(session, "f1")
    make_segmentation(session, image, feature, creator)
    session.refresh(image)
    assert any("segmentation" in r for r in blocking_dependents(image))


def test_repair_fixes_and_audits(image_graph):
    session, series, device, backend = image_graph
    image = make_image(session, series, device, backend, "img-fix")
    image.Rows_y = 10
    image.Columns_x = 20
    session.flush()
    array = np.zeros((8, 9, 3), dtype=np.uint8)

    with patch.object(ImageInstance, "load_pixel_array", return_value=array):
        summary = repair_image_dimensions_for_ids(
            session, [image.ImageInstanceID], dry_run=False
        )

    assert summary.fixed == 1
    assert image.Rows_y == 8 and image.Columns_x == 9 and image.NrOfFrames == 1
    row = session.query(AuditLog).one()
    assert row.TrustedPath == TRUSTED_PATH
    assert row.Action == "UPDATE"
    assert row.Entity == "ImageInstance"
    assert row.EntityID == str(image.ImageInstanceID)
    assert row.Changes["old"]["Rows_y"] == 10
    assert row.Changes["new"]["Rows_y"] == 8


def test_repair_skips_ok(image_graph):
    session, series, device, backend = image_graph
    image = make_image(session, series, device, backend, "img-ok")
    image.Rows_y = 8
    image.Columns_x = 9
    image.NrOfFrames = 1
    session.flush()
    array = np.zeros((8, 9, 3), dtype=np.uint8)
    with patch.object(ImageInstance, "load_pixel_array", return_value=array):
        summary = repair_image_dimensions_for_ids(
            session, [image.ImageInstanceID], dry_run=False
        )
    assert summary.ok == 1
    assert session.query(AuditLog).count() == 0


def test_repair_blocks_with_segmentation(image_graph):
    session, series, device, backend = image_graph
    image = make_image(session, series, device, backend, "img-seg")
    # Keep factory default 4x4 so segmentation consistency checks pass
    creator = make_creator(session, "c2")
    feature = make_feature(session, "f2")
    make_segmentation(session, image, feature, creator)
    session.expire(image, ["Segmentations"])
    array = np.zeros((8, 9), dtype=np.uint8)
    with patch.object(ImageInstance, "load_pixel_array", return_value=array):
        summary = repair_image_dimensions_for_ids(
            session, [image.ImageInstanceID], dry_run=False
        )
    assert summary.blocked == 1
    assert image.Rows_y == 4
    assert session.query(AuditLog).count() == 0


def test_repair_dry_run_does_not_persist(image_graph):
    session, series, device, backend = image_graph
    image = make_image(session, series, device, backend, "img-dry")
    image.Rows_y = 10
    image.Columns_x = 20
    session.flush()
    array = np.zeros((8, 9), dtype=np.uint8)
    with patch.object(ImageInstance, "load_pixel_array", return_value=array):
        summary = repair_image_dimensions_for_ids(
            session, [image.ImageInstanceID], dry_run=True
        )
    assert summary.fixed == 1
    assert image.Rows_y == 10
    assert session.query(AuditLog).count() == 0


def test_apply_dimensions_sets_frames_to_one_for_2d():
    class _Img:
        Rows_y = 1
        Columns_x = 1
        NrOfFrames = None

    img = _Img()
    changes = apply_dimensions(
        img, dimensions_from_array(np.zeros((4, 5)))
    )
    assert img.NrOfFrames == 1
    assert changes["new"]["NrOfFrames"] == 1
