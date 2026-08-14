"""Tests for ETDRS input resolution via ModelInputSpec."""

from __future__ import annotations

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    AttributesModel,
)
from eyened_orm.commands.test_targets import _import_images
from eyened_orm.inference.etdrs_summary import resolve_etdrs_inputs


def _seed_keypoints(
    session,
    image_id: int,
    *,
    version: str,
    value_json: dict | None = None,
) -> AttributeValue:
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_Keypoints",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )
    model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_Keypoints", "Version": version},
        update_values={"Description": "kpts"},
    )
    av = AttributeValue(
        AttributeID=attr.AttributeID,
        ModelID=model.ModelID,
        ImageInstanceID=image_id,
        ValueJSON=value_json
        or {"fovea_xy": [1.0, 2.0], "disc_edge_xy": [3.0, 4.0]},
    )
    session.add(av)
    session.flush()
    return av


def _seed_odfd(
    session,
    image_id: int,
    *,
    version: str,
    value: float = 0.5,
) -> AttributeValue:
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "CFI_ODFD",
            "AttributeDataType": AttributeDataType.Float,
        },
    )
    model = AttributesModel.get_or_create(
        session,
        match_by={"ModelName": "CFI_ODFD", "Version": version},
        update_values={"Description": "odfd"},
    )
    av = AttributeValue(
        AttributeID=attr.AttributeID,
        ModelID=model.ModelID,
        ImageInstanceID=image_id,
        ValueFloat=value,
    )
    session.add(av)
    session.flush()
    return av


def test_resolve_etdrs_inputs_picks_highest_version(session):
    _proj, images = _import_images(session, count=1)
    image_id = images[0].ImageInstanceID

    _seed_keypoints(session, image_id, version="0.9.0")
    newer_kpts = _seed_keypoints(
        session,
        image_id,
        version="Eyened/vascx/discedge/discedge_july24+Eyened/vascx/fovea/fovea_july24",
        value_json={"fovea_xy": [10.0, 20.0], "disc_edge_xy": [30.0, 40.0]},
    )
    _seed_odfd(session, image_id, version="0.9.0", value=0.1)
    newer_odfd = _seed_odfd(
        session,
        image_id,
        version="1.0.0",
        value=0.8,
    )
    session.commit()

    resolved = resolve_etdrs_inputs(session, image_id)

    assert resolved is not None
    keypoints_av, odfd_av = resolved
    assert keypoints_av.AttributeValueID == newer_kpts.AttributeValueID
    assert odfd_av.AttributeValueID == newer_odfd.AttributeValueID


def test_resolve_etdrs_inputs_returns_none_when_input_missing(session):
    _proj, images = _import_images(session, count=1)
    image_id = images[0].ImageInstanceID
    _seed_keypoints(session, image_id, version="1.0")
    session.commit()

    assert resolve_etdrs_inputs(session, image_id) is None
