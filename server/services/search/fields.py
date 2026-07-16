"""The search vocabulary: UI labels, their ORM attributes, and the field signature.

Lives in ``services/`` because it has consumers in two layers -- ``routes/``
types its Pydantic ``variable`` fields with the Literals here, and
``SearchService`` resolves labels against the maps here. A symbol used by two
layers must live in the lower one.
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from eyened_orm import (
    Creator,
    DeviceModel,
    Feature,
    FormAnnotation,
    FormSchema,
    ImageInstance,
    Patient,
    Project,
    Segmentation,
    Study,
    Tag,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import aliased

ActiveSegmentation = aliased(
    Segmentation,
    select(Segmentation)
    .filter(~Segmentation.Inactive)
    .subquery(name="active_segmentation"),
    name="active_segmentation",
)
ActiveFormAnnotation = aliased(
    FormAnnotation,
    select(FormAnnotation)
    .filter(~FormAnnotation.Inactive)
    .subquery(name="active_form_annot"),
    name="active_form_annot",
)
SegCreator = aliased(Creator, name="seg_creator")
FormCreator = aliased(Creator, name="form_creator")
SegTag = aliased(Tag, name="seg_tag")
FormTag = aliased(Tag, name="form_tag")
InstTag = aliased(Tag, name="image_tag")
StudyTag = aliased(Tag, name="study_tag")

# list of properties that are searchable with identifier and mapped ORM property
searchable_fields = Literal[
    "Image DBID",
    "Laterality",
    "Modality",
    "ETDRS Field",
    "Color Fundus Quality",
    "Study Date",
    "Patient Identifier",
    "Patient Sex",
    "Patient Birthdate",
    "Project Name",
    "Device Model ID",
    "Segmentation Feature Name",  # backward-compat
    "Segmentation Creator Name",
    "Segmentation Tag Name",
    "Form Schema Name",
    "Form Creator Name",
    "Form Tag Name",
    "Image Tag Name",
]

operators = Literal[">", "<", ">=", "<=", "==", "!=", "IN", "IS NULL"]

instance_search_fields_map: Dict[searchable_fields, Any] = {
    "Image DBID": ImageInstance.ImageInstanceID,
    "Laterality": ImageInstance.Laterality,
    "Modality": ImageInstance.Modality,
    "ETDRS Field": ImageInstance.ETDRSField,
    "Color Fundus Quality": ImageInstance.CFQuality,
    "Study Date": Study.StudyDate,
    "Patient Identifier": Patient.PatientIdentifier,
    "Patient Sex": Patient.Sex,
    "Patient Birthdate": Patient.BirthDate,
    "Project Name": Project.ProjectName,
    "Device Model ID": DeviceModel.DeviceModelID,
    "Segmentation Feature Name": Feature.FeatureName,
    "Segmentation Creator Name": SegCreator.CreatorName,
    "Segmentation Tag Name": SegTag.TagName,
    "Form Schema Name": FormSchema.SchemaName,
    "Form Creator Name": FormCreator.CreatorName,
    "Form Tag Name": FormTag.TagName,
    "Image Tag Name": InstTag.TagName,
}

# Study search
study_searchable_fields = Literal[
    "Study Date",
    "Study Description",
    "Study Round",
    "Patient Identifier",
    "Patient Sex",
    "Patient Birthdate",
    "Project Name",
    "Form Schema Name",
    "Form Creator Name",
    "Form Tag Name",
    "Study Tag Name",
]

study_search_fields_map: Dict[study_searchable_fields, Any] = {
    "Study Date": Study.StudyDate,
    "Study Description": Study.StudyDescription,
    "Study Round": Study.StudyRound,
    "Patient Identifier": Patient.PatientIdentifier,
    "Patient Sex": Patient.Sex,
    "Patient Birthdate": Patient.BirthDate,
    "Project Name": Project.ProjectName,
    "Form Schema Name": FormSchema.SchemaName,
    "Form Creator Name": FormCreator.CreatorName,
    "Form Tag Name": FormTag.TagName,
    "Study Tag Name": StudyTag.TagName,
}

# Order-by options for instances
instance_order_by_fields = Literal[
    "Study Date",
    "Patient Birthdate",
    "Date Inserted",
]

instance_order_by_fields_map: Dict[instance_order_by_fields, Any] = {
    "Study Date": Study.StudyDate,
    "Patient Birthdate": Patient.BirthDate,
    "Date Inserted": ImageInstance.DateInserted,
}

# Order-by options for studies
study_order_by_fields = Literal[
    "Study Date",
    "Patient Birthdate",
    "Date Inserted",
]

study_order_by_fields_map: Dict[study_order_by_fields, Any] = {
    "Study Date": Study.StudyDate,
    "Patient Birthdate": Patient.BirthDate,
    "Date Inserted": Study.DateInserted,
}


class SignatureField(BaseModel):
    """Signature descriptor for a searchable field."""

    name: str
    # Either a primitive type marker or an enum of allowed values
    values: str | list[str]  # 'string' | 'int' | 'float' | 'date' | string[]
    type: Literal["default", "attribute"] = "default"
    model: Optional[str] = None
    feature: Optional[str] = None  # NEW: feature name for segmentation-based attributes
    nullable: bool = False
    # Free-text field that additionally supports matching several values at once
    # (rendered as an IN / multi-value editor on the client).
    multi: bool = False
