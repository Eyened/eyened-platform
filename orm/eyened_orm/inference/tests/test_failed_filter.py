"""Tests for --failed retry targeting on CFI attribute pipelines."""

from __future__ import annotations

from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.cfi_roi import CFI_ROI


def test_default_filter_skips_failed_images(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    pipeline = CFI_ROI(session, n_workers=1)
    pipeline._save_failure(image.ImageInstanceID)
    session.commit()

    filtered = pipeline.filter_image_ids([image.ImageInstanceID])
    assert filtered == set()


def test_failed_scope_includes_only_failed_images(session):
    _proj, images = _import_images(session, count=2)
    failed_image, ok_image = images

    pipeline = CFI_ROI(session, n_workers=1)
    pipeline._save_failure(failed_image.ImageInstanceID)
    pipeline._save_result(ok_image.ImageInstanceID, {"center": [1, 2], "radius": 3})
    session.commit()

    scoped = pipeline.failed_image_ids_in_scope(
        [failed_image.ImageInstanceID, ok_image.ImageInstanceID]
    )
    assert scoped == {failed_image.ImageInstanceID}


def test_failed_filter_retries_failed_and_skips_succeeded(session):
    _proj, images = _import_images(session, count=2)
    failed_image, ok_image = images

    pipeline = CFI_ROI(session, n_workers=1)
    pipeline._save_failure(failed_image.ImageInstanceID)
    pipeline._save_result(
        ok_image.ImageInstanceID, {"center": [1, 2], "radius": 3, "lines": {}}
    )
    session.commit()

    scoped = pipeline.failed_image_ids_in_scope(
        [failed_image.ImageInstanceID, ok_image.ImageInstanceID]
    )
    filtered = pipeline.filter_image_ids(scoped, failed=True)

    assert filtered == {failed_image.ImageInstanceID}


def test_failed_filter_excludes_succeeded_even_with_older_failed_row(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    from eyened_orm import AttributeDefinition, AttributeValue, AttributesModel

    pipeline = CFI_ROI(session, n_workers=1)
    legacy_model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ROI", "Version": "1.0"},
        update_values={"Description": "legacy"},
    )
    session.add(
        AttributeValue(
            AttributeID=pipeline.attr_definition.AttributeID,
            ModelID=legacy_model.ModelID,
            ImageInstanceID=image.ImageInstanceID,
            ValueJSON=None,
        )
    )
    pipeline._save_result(
        image.ImageInstanceID, {"center": [1, 2], "radius": 3, "lines": {}}
    )
    session.commit()

    scoped = pipeline.failed_image_ids_in_scope([image.ImageInstanceID])
    assert scoped == {image.ImageInstanceID}

    filtered = pipeline.filter_image_ids(scoped, failed=True)
    assert filtered == set()
