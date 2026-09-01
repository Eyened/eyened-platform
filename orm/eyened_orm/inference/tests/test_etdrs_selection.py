"""Tests for ETDRS candidate selection (stored ModelSegmentation only, chunked)."""

from __future__ import annotations

from eyened_orm import (
    AttributeDataType,
    AttributeDefinition,
    AttributeValue,
    Feature,
    ModelSegmentation,
    SegmentationModel,
)
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.etdrs_summary import image_ids_with_segmentation_output
from eyened_orm.reports.etdrs_model import ETDRSModelProcessor
from eyened_orm.segmentation import DataRepresentation, Datatype


def _seed_seg_model(session, name: str = "Drusen", version: str = "3") -> SegmentationModel:
    feature = Feature.get_or_create(session, match_by={"FeatureName": name})
    return SegmentationModel.get_or_create(
        session,
        match_by={
            "FeatureID": feature.FeatureID,
            "ModelName": name,
            "Version": version,
        },
    )


def _prepare_image_dims(image, *, height: int = 8, width: int = 8) -> None:
    image.Rows_y = height
    image.Columns_x = width
    image.NrOfFrames = 1


def _seed_model_seg(session, image, model, *, zarr_index: int | None) -> ModelSegmentation:
    _prepare_image_dims(image)
    ms = ModelSegmentation(
        ImageInstanceID=image.ImageInstanceID,
        ModelID=model.ModelID,
        ZarrArrayIndex=zarr_index,
        Depth=1,
        Height=image.Rows_y,
        Width=image.Columns_x,
        SparseAxis=0,
        DataType=Datatype.R8,
        DataRepresentation=DataRepresentation.Probability,
        Threshold=0.5,
    )
    session.add(ms)
    session.flush()
    return ms


def test_image_ids_with_segmentation_output_keeps_only_stored_maps(session):
    _proj, images = _import_images(session, count=4)
    model = _seed_seg_model(session)
    other = _seed_seg_model(session, name="Other", version="1")

    stored, empty, _no_seg, other_model = images
    _seed_model_seg(session, stored, model, zarr_index=0)
    _seed_model_seg(session, empty, model, zarr_index=None)
    _seed_model_seg(session, other_model, other, zarr_index=1)
    session.commit()

    found = image_ids_with_segmentation_output(
        session,
        model.ModelID,
        {im.ImageInstanceID for im in images},
    )

    assert found == {stored.ImageInstanceID}


def test_image_ids_with_segmentation_output_chunks_without_dropping_ids(session):
    _proj, images = _import_images(session, count=5)
    model = _seed_seg_model(session)
    for image in images:
        _seed_model_seg(session, image, model, zarr_index=1)
    session.commit()

    image_ids = {im.ImageInstanceID for im in images}
    found = image_ids_with_segmentation_output(
        session,
        model.ModelID,
        image_ids,
        chunk_size=2,
    )

    assert found == image_ids


def test_get_processed_image_ids_chunks_without_dropping_ids(session):
    _proj, images = _import_images(session, count=5)
    model = _seed_seg_model(session)
    processor = ETDRSModelProcessor(session)
    attr = AttributeDefinition.get_or_create(
        session,
        match_by={
            "AttributeName": "ETDRS area",
            "AttributeDataType": AttributeDataType.JSON,
        },
    )

    for image in images:
        ms = _seed_model_seg(session, image, model, zarr_index=1)
        session.add(
            AttributeValue(
                AttributeID=attr.AttributeID,
                ModelID=processor.model.ModelID,
                ModelSegmentationID=ms.ModelSegmentationID,
                ValueJSON={"grid_area": 1.0},
            )
        )
    session.commit()

    image_ids = {im.ImageInstanceID for im in images}
    found = processor.get_processed_image_ids(
        model.ModelID, image_ids, chunk_size=2
    )

    assert found == image_ids
