"""
Pydantic DTOs for EyeNed Platform
Auto-generated from TypeScript datamodel mappings

This file contains DTOs that represent:
1. Database field representations (with string field names as they appear in DB)
2. Frontend object representations (with property names as used in TypeScript)
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, get_origin

from pydantic import BaseModel, create_model

# Type aliases matching TypeScript types
Laterality = Literal["L", "R"]
Sex = Literal["M", "F"]
AnnotationTypeInterpretation = Literal[
    "", "R/G mask", "Binary mask", "Label numbers", "Probability", "Layer bits"
]
AnatomicRegion = str  # Based on database field
VesselType = Literal["Artery", "Vein", "Vessel"]


def model_omit(model, omit_fields):
    """
    Returns a new Pydantic model class with the specified fields omitted.
    :param model: The original Pydantic model class.
    :param omit_fields: A set or list of field names to omit.
    """
    fields = {
        name: (field.outer_type_, field.default)
        for name, field in model.__fields__.items()
        if name not in omit_fields
    }
    return create_model(f"{model.__name__}Omit", **fields)


def model_pick(model, pick_fields):
    """
    Returns a new Pydantic model class with only the specified fields included.
    :param model: The original Pydantic model class.
    :param pick_fields: A set or list of field names to include.
    """
    fields = {
        name: (field.outer_type_, field.default)
        for name, field in model.__fields__.items()
        if name in pick_fields
    }
    return create_model(f"{model.__name__}Pick", **fields)


def model_partial(model):
    """
    Returns a new Pydantic model class with all fields made Optional and defaulting to None.
    :param model: The original Pydantic model class.
    """
    fields = {}
    for name, field in model.__fields__.items():
        # If already Optional, keep as is; else wrap in Optional
        field_type = field.outer_type_
        if get_origin(field_type) is Optional:
            optional_type = field_type
        else:
            optional_type = Optional[field_type]
        fields[name] = (optional_type, None)
    return create_model(f"{model.__name__}Partial", **fields)


# Utility DTOs
class Position2D(BaseModel):
    x: float
    y: float


class ROI(BaseModel):
    cx: float
    cy: float
    radius: float
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    w: float
    h: float


class Keypoints(BaseModel):
    fovea_xy: tuple[float, float]
    disc_edge_xy: tuple[float, float]
    prep_fovea_xy: tuple[float, float]
    prep_disc_edge_xy: tuple[float, float]


# === CREATOR ===
class CreatorBase(BaseModel):
    """Creator frontend object"""

    name: str
    msn: Optional[str] = None
    is_human: bool
    description: Optional[str] = None
    version: Optional[str] = None
    role: Optional[Any] = None


class CreatorInput(CreatorBase):
    pass


class CreatorOutput(CreatorBase):
    id: int
    date_inserted: datetime


class CreatorMetadata(BaseModel):
    id: int
    name: str


# === Project, Patient, Study, Series ===
class ProjectBase(BaseModel):
    name: str
    external: bool
    description: Optional[str] = None


class ProjectOutput(ProjectBase):
    id: int


class PatientBase(BaseModel):
    identifier: str
    birth_date: Optional[date] = None
    sex: Optional[Sex] = None


class PatientOutput(PatientBase):
    id: int


class StudyBase(BaseModel):
    description: Optional[str] = None
    date: datetime
    study_instance_uid: Optional[str] = None


class StudyOutput(StudyBase):
    id: int


class SeriesBase(BaseModel):
    series_number: Optional[int] = None
    series_instance_uid: str


class SeriesOutput(SeriesBase):
    id: int


class DeviceModelBase(BaseModel):
    manufacturer: str
    model: str


class DeviceModelInput(DeviceModelBase):
    pass


class DeviceModelOutput(DeviceModelBase):
    id: int


class DeviceInstanceBase(BaseModel):
    device_model_id: int
    serial_number: Optional[str] = None
    description: Optional[str] = None


class DeviceInstanceInput(DeviceInstanceBase):
    pass


class DeviceInstanceOutput(DeviceInstanceBase):
    id: int


class DeviceMerged(DeviceInstanceBase, DeviceModelBase):
    pass


class ScanBase(BaseModel):
    mode: str


class ScanInput(ScanBase):
    pass


class ScanOutput(ScanBase):
    id: int


class InstanceBase(BaseModel):
    """Instance frontend object"""

    sop_instance_uid: str
    dataset_identifier: str
    thumbnail_identifier: str
    thumbnail_path: str
    modality: str
    dicom_modality: str
    etdrs_field: str
    angio_graphy: str
    laterality: Laterality
    anatomic_region: AnatomicRegion
    rows: int
    columns: int
    nr_of_frames: int
    resolution_horizontal: float
    resolution_vertical: float
    resolution_axial: float
    cf_roi: Optional[ROI] = None
    cf_keypoints: Optional[Keypoints] = None
    cf_quality: Optional[float] = None
    date_inserted: datetime
    date_modified: Optional[datetime] = None
    date_preprocessed: Optional[datetime] = None


class InstanceInput(InstanceBase):
    id: int

    series_id: int

    scan_id: Optional[int] = None
    device_instance_id: Optional[int] = None


class InstanceOutput(InstanceBase):
    id: int
    project: ProjectOutput
    patient: PatientOutput
    study: StudyOutput
    series: SeriesOutput
    device: DeviceMerged
    scan: ScanOutput

    date_inserted: datetime
    date_modified: Optional[datetime] = None
    date_preprocessed: Optional[datetime] = None


# === TAG ===
class TagBase(BaseModel):
    name: str


class TagInput(TagBase):
    pass


class TagOutput(TagBase):
    id: int


# === ANNOTATION TYPE ===
class AnnotationTypeBase(BaseModel):
    name: str
    interpretation: str


class AnnotationTypeInput(AnnotationTypeBase):
    pass


class AnnotationTypeOutput(AnnotationTypeBase):
    id: int


# === FEATURE ===
class FeatureBase(BaseModel):
    name: str
    modality: Optional[str] = None


class FeatureInput(FeatureBase):
    pass


class FeatureOutput(FeatureBase):
    id: int
    date_inserted: datetime


# === ANNOTATION ===
class AnnotationBase(BaseModel):
    patient_id: int
    study_id: Optional[int] = None
    series_id: Optional[int] = None
    image_instance_id: Optional[int] = None
    creator_id: int
    feature_id: int
    annotation_type_id: int
    annotation_reference_id: Optional[int] = None
    inactive: bool = False


class AnnotationInput(AnnotationBase):
    pass


class AnnotationOutput(AnnotationBase):
    id: int
    date_inserted: datetime


# === ANNOTATION DATA ===
class AnnotationDataBase(BaseModel):
    annotation_id: int
    scan_nr: int
    dataset_identifier: str
    media_type: str
    value_int: Optional[int] = None
    value_float: Optional[float] = None


class AnnotationDataInput(AnnotationDataBase):
    pass


class AnnotationDataOutput(AnnotationDataBase):
    date_modified: Optional[datetime] = None


# === FORM SCHEMA ===
class FormSchemaBase(BaseModel):
    name: Optional[str] = None
    schema: Optional[Dict[str, Any]] = None


class FormSchemaInput(FormSchemaBase):
    pass


class FormSchemaOutput(FormSchemaBase):
    id: int


# === FORM ANNOTATION ===
class FormAnnotationBase(BaseModel):
    form_schema_id: int
    patient_id: int
    study_id: Optional[int] = None
    image_instance_id: Optional[int] = None
    creator_id: int
    sub_task_id: Optional[int] = None
    form_data: Optional[Dict[str, Any]] = None
    form_annotation_reference_id: Optional[int] = None
    inactive: bool = False


class FormAnnotationInput(FormAnnotationBase):
    pass


class FormAnnotationOutput(FormAnnotationBase):
    id: int
    date_inserted: datetime
    date_modified: Optional[datetime] = None


# === TASK DEFINITION ===
class TaskDefinitionBase(BaseModel):
    name: str


class TaskDefinitionInput(TaskDefinitionBase):
    pass


class TaskDefinitionOutput(TaskDefinitionBase):
    id: int
    date_inserted: datetime


# === TASK STATE ===
class TaskStateBase(BaseModel):
    name: str


class TaskStateInput(TaskStateBase):
    pass


class TaskStateOutput(TaskStateBase):
    id: int


# === TASK ===
class TaskBase(BaseModel):
    name: str
    description: Optional[str] = None
    contact_id: Optional[int] = None
    task_definition_id: int
    task_state_id: int


class TaskInput(TaskBase):
    pass


class TaskOutput(TaskBase):
    id: int
    date_inserted: datetime


# === SUB TASK ===
class SubTaskBase(BaseModel):
    task_id: int
    task_state_id: int
    creator_id: Optional[int] = None


class SubTaskInput(SubTaskBase):
    pass


class SubTaskOutput(SubTaskBase):
    id: int


# === SUB TASK IMAGE LINK ===
class SubTaskImageLinkBase(BaseModel):
    sub_task_id: int
    image_instance_id: int


class SubTaskImageLinkInput(SubTaskImageLinkBase):
    pass


class SubTaskImageLinkOutput(SubTaskImageLinkBase):
    id: int


# === CONTACT ===
class ContactBase(BaseModel):
    name: str
    email: str
    institute: Optional[str] = None


class ContactInput(ContactBase):
    pass


class ContactOutput(ContactBase):
    id: int


# === SOURCE INFO ===
class SourceInfoBase(BaseModel):
    name: str
    source_path: str
    thumbnail_path: str


class SourceInfoInput(SourceInfoBase):
    pass


class SourceInfoOutput(SourceInfoBase):
    id: int


# === MODALITY TABLE ===
class ModalityTableBase(BaseModel):
    tag: str


class ModalityTableInput(ModalityTableBase):
    pass


class ModalityTableOutput(ModalityTableBase):
    id: int


# === SEGMENTATION (LEGACY) ===
class SegmentationBase(BaseModel):
    id: int
    image_id: int
    feature_id: int
    reference_id: Optional[int] = None


class SegmentationInput(SegmentationBase):
    pass


class SegmentationOutput(SegmentationBase):
    creator_id: int
    date_inserted: datetime


### BROWSER DTOs
class SeriesBrowser(SeriesOutput):
    instances: List[InstanceOutput]

class StudyBrowser(StudyOutput):
    patient: PatientOutput
    series: List[SeriesOutput]
