"""
Pydantic DTOs for EyeNed Platform
Auto-generated from TypeScript datamodel mappings

This file contains DTOs that represent:
1. Database field representations (with string field names as they appear in DB)
2. Frontend object representations (with property names as used in TypeScript)
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional, get_origin

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


class ProjectOutput(BaseModel):
    id: int


class PatientBase(BaseModel):
    identifier: str
    birth_date: Optional[datetime] = None
    sex: Optional[Sex] = None


class PatientOutput(BaseModel):
    id: int


class StudyBase(BaseModel):
    description: Optional[str] = None
    date: datetime
    study_instance_uid: Optional[str] = None


class StudyOutput(BaseModel):
    id: int


class SeriesBase(BaseModel):
    series_number: Optional[int] = None
    series_instance_uid: str


class SeriesOutput(BaseModel):
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


# === FORM ANNOTATION ===
class FormAnnotationBase(BaseModel):
    id: int
    form_schema_id: int
    patient_id: int
    study_id: Optional[int] = None
    image_id: Optional[int] = None

    form_data: Optional[Dict[str, Any]] = None


class InputFormAnnotation(FormAnnotationBase):
    pass


class OutputFormAnnotation(FormAnnotationBase):
    creator: CreatorMetadata
    date_inserted: datetime
    date_modified: Optional[datetime] = None


# === SEGMENTATION ===
class Feature(BaseModel):
    """Feature frontend object"""

    id: int
    name: str


class SegmentationBase(BaseModel):
    id: int
    image_id: int

    feature_id: int
    reference_id: Optional[int] = None


class SegmentationInput(SegmentationBase):
    pass


class SegmentationOutput(SegmentationBase):
    creator: CreatorMetadata
    date_inserted: datetime
