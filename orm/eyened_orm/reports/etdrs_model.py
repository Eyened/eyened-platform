from eyened_orm import (
    AttributeDataType,
    Segmentation,
    ModelSegmentation,
    AttributesModel,
    AttributeDefinition,
    AttributeValue,
)
from eyened_orm.reports.etdrs_masks import ETDRS_masks
from sqlalchemy.orm import Session, object_session
from typing import Set

model_name = "ETDRS area"
version = "1"
description = "Summarize segmentation feature area in ETDRS grid subfields"
attribute_name = "ETDRS area"
attribute_data_type = AttributeDataType.Float


def _get_etdrs_mask(segmentation, keypoints_attr, odfd_attr):
    image = segmentation.ImageInstance
    h, w = image.Rows_y, image.Columns_x
    laterality = image.Laterality.value
    try:
        fovea_x, fovea_y = keypoints_attr.value["fovea_xy"]
    except KeyError as e:
        raise KeyError("Fovea coordinates not found in attribute value") from e

    try:
        # 0.76 * odfd = 3 mm
        # resolution in mm/pix
        resolution = 3 / (0.76 * odfd_attr.value)
    except KeyError as e:
        raise KeyError("Resolution not found in attribute value") from e

    return ETDRS_masks(h, w, fovea_x, fovea_y, resolution, laterality)


def process_etdrs_model(
    model: AttributesModel,
    attribute_definition: AttributeDefinition,
    segmentation: Segmentation | ModelSegmentation,
    keypoints_attr: AttributeValue,
    odfd_attr: AttributeValue,  # TODO: alternatively, get resolution from image columns
):
    session = object_session(segmentation)
    if session is None:
        raise ValueError("Session not found for segmentation")

    image = segmentation.ImageInstance
    etdrs_mask = _get_etdrs_mask(segmentation, keypoints_attr, odfd_attr)
    h, w = image.Rows_y, image.Columns_x
    binary_mask = segmentation.binary_mask

    assert binary_mask.shape == (h, w), "Shape mismatch"

    value = etdrs_mask.get_summary(segmentation.binary_mask, ETDRS_masks.all_fields)

    av = AttributeValue.upsert(
        session,
        match_by={
            "ModelID": model.ModelID,
            "AttributeID": attribute_definition.AttributeID,
            "ImageInstanceID": image.ImageInstanceID,
        },
        update_values={"ValueJSON": value},
    )
    # provenance tracking
    av.InputValues = {keypoints_attr, odfd_attr}
    session.add(av)
    session.flush()
    return av


class ETDRSModelProcessor:

    def __init__(self, session: Session):
        self.session = session
        self.model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": model_name, "Version": version},
            create_kwargs={"Description": description},
        )

        self.attribute_definition = AttributeDefinition.get_or_create(
            session,
            match_by={
                "AttributeName": attribute_name,
                "AttributeDataType": attribute_data_type,
            },
        )

    def get_processed_image_ids(self, image_ids: Set[int]) -> Set[int]:
        return set(
            AttributeValue.select(
                self.session,
                "ImageInstanceID",
                AttributeID=self.attribute_definition.AttributeID,
                ModelID=self.model.ModelID,
                ImageInstanceID=image_ids,
            )
        )

    def process(
        self,
        segmentation: Segmentation | ModelSegmentation,
        keypoints_attr: AttributeValue,
        odfd_attr: AttributeValue,
    ):
        return process_etdrs_model(
            self.model,
            self.attribute_definition,
            segmentation,
            keypoints_attr,
            odfd_attr,
        )
