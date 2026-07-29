"""Tests for version-aware attribute value lookup."""

from __future__ import annotations

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.test_targets import _import_images
from eyened_orm.inference.model_inputs import (
    ModelInputSpec,
    resolve_input_attribute_value,
    select_attribute_value,
)


def _seed_cfi_roi_values(
    session,
    image_id: int,
    *,
    versions: dict[str, dict | None],
) -> dict[str, AttributeValue]:
    roi_attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ROI",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    result: dict[str, AttributeValue] = {}
    for version, value_json in versions.items():
        roi_model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": "CFI_ROI", "Version": version},
            update_values={"Description": f"roi {version}"},
        )
        av = AttributeValue(
            AttributeID=roi_attr.AttributeID,
            ModelID=roi_model.ModelID,
            ImageInstanceID=image_id,
            ValueJSON=value_json,
        )
        session.add(av)
        result[version] = av
    session.commit()
    return result


def test_select_attribute_value_picks_highest_version(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    seeded = _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={
            "1.0": {"center": [1, 1], "radius": 1, "lines": {}},
            "2.0": {"center": [2, 2], "radius": 2, "lines": {}},
        },
    )
    session.refresh(image)

    selected = select_attribute_value(
        image.AttributeValues, attribute_name="CFI_ROI"
    )
    assert selected is not None
    assert selected.AttributeValueID == seeded["2.0"].AttributeValueID
    assert selected.ValueJSON["center"] == [2, 2]


def test_select_attribute_value_picks_highest_model_id_not_lexicographic_version(
    session,
):
    """Legacy opaque labels like july24 must not beat a later-registered HF id."""
    _proj, images = _import_images(session, count=1)
    image = images[0]

    seeded = _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={
            "july24": {"center": [1, 1], "radius": 1, "lines": {}},
            "Eyened/vascx/odfd/odfd_march25": {
                "center": [2, 2],
                "radius": 2,
                "lines": {},
            },
        },
    )
    session.refresh(image)

    assert seeded["Eyened/vascx/odfd/odfd_march25"].ModelID > seeded["july24"].ModelID

    selected = select_attribute_value(
        image.AttributeValues, attribute_name="CFI_ROI"
    )
    assert selected is not None
    assert selected.AttributeValueID == seeded[
        "Eyened/vascx/odfd/odfd_march25"
    ].AttributeValueID


def test_select_attribute_value_skips_rows_without_producing_model(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    seeded = _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={"1.0": {"center": [1, 1], "radius": 1, "lines": {}}},
    )
    session.refresh(image)

    roi_attr = AttributeDefinition.by_column(
        session, AttributeName="CFI_ROI", AttributeDataType=AttributeDataType.JSON
    )
    session.add(
        AttributeValue(
            AttributeID=roi_attr.AttributeID,
            ModelID=None,
            ImageInstanceID=image.ImageInstanceID,
            ValueJSON={"center": [9, 9], "radius": 9, "lines": {}},
        )
    )
    session.commit()
    session.refresh(image)

    selected = select_attribute_value(
        image.AttributeValues, attribute_name="CFI_ROI"
    )
    assert selected is not None
    assert selected.AttributeValueID == seeded["1.0"].AttributeValueID


def test_select_attribute_value_respects_min_version(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={
            "1.0": {"center": [1, 1], "radius": 1, "lines": {}},
            "2.0": {"center": [2, 2], "radius": 2, "lines": {}},
        },
    )
    session.refresh(image)

    selected = select_attribute_value(
        image.AttributeValues,
        attribute_name="CFI_ROI",
        producing_model_name="CFI_ROI",
        min_version="2.0",
    )
    assert selected is not None
    assert selected.ValueJSON["center"] == [2, 2]


def test_select_attribute_value_min_version_excludes_lower_versions(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={"1.0": {"center": [1, 1], "radius": 1, "lines": {}}},
    )
    session.refresh(image)

    none = select_attribute_value(
        image.AttributeValues,
        attribute_name="CFI_ROI",
        producing_model_name="CFI_ROI",
        min_version="2.0",
    )
    assert none is None


def test_select_attribute_value_skips_failed_rows(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    seeded = _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={
            "1.0": None,
            "2.0": {"center": [2, 2], "radius": 2, "lines": {}},
        },
    )
    session.refresh(image)

    selected = select_attribute_value(
        image.AttributeValues, attribute_name="CFI_ROI"
    )
    assert selected is not None
    assert selected.AttributeValueID == seeded["2.0"].AttributeValueID


def test_find_attribute_value_matches_resolve_input(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    seeded = _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={
            "1.0": {"center": [1, 1], "radius": 1, "lines": {}},
            "2.0": {"center": [2, 2], "radius": 2, "lines": {}},
        },
    )
    session.refresh(image)

    from_db = resolve_input_attribute_value(
        session,
        image_id=image.ImageInstanceID,
        spec=ModelInputSpec("CFI_ROI", "CFI_ROI", "1.0"),
    )
    from_mixin = image.find_attribute_value(
        attribute_name="CFI_ROI",
        producing_model_name="CFI_ROI",
        min_version="1.0",
    )

    assert from_mixin is not None
    assert from_db is not None
    assert from_mixin.AttributeValueID == from_db.AttributeValueID
    assert from_mixin.AttributeValueID == seeded["2.0"].AttributeValueID


def test_get_attribute_value_returns_stored_value(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={"2.0": {"center": [9, 9], "radius": 9, "lines": {}}},
    )
    session.refresh(image)

    value = image.get_attribute_value(attribute_name="CFI_ROI")
    assert value == {"center": [9, 9], "radius": 9, "lines": {}}


def test_image_attrs_uses_highest_version(session):
    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={
            "1.0": {"center": [1, 1], "radius": 1, "lines": {}},
            "2.0": {"center": [5, 5], "radius": 5, "lines": {}},
        },
    )
    session.refresh(image)

    _attrs_flat, attrs_by_model = image.attrs
    assert attrs_by_model["CFI_ROI"]["CFI_ROI"]["center"] == [5, 5]


def test_image_roi_uses_highest_version(session, caplog):
    import logging

    _proj, images = _import_images(session, count=1)
    image = images[0]

    _seed_cfi_roi_values(
        session,
        image.ImageInstanceID,
        versions={
            "1.0": {"center": [1, 1], "radius": 1, "lines": {}},
            "2.0": {"center": [5, 5], "radius": 5, "lines": {}},
        },
    )
    session.refresh(image)

    with caplog.at_level(logging.WARNING, logger="eyened_orm.image_instance"):
        roi = image.roi

    assert roi is not None
    assert roi["center"] == [5, 5]
    assert caplog.text == ""
