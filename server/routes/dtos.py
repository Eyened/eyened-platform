"""
Pydantic DTOs for EyeNed Platform
Auto-generated from TypeScript datamodel mappings

This file contains DTOs that represent:
1. Database field representations (with string field names as they appear in DB)
2. Frontend object representations (with property names as used in TypeScript)
"""
from datetime import datetime
from typing import Dict, Optional, List, Literal, Union, Any
from pydantic import BaseModel, Field

# Type aliases matching TypeScript types
Laterality = Literal['L', 'R']
Sex = Literal['M', 'F']
AnnotationTypeInterpretation = Literal['', 'R/G mask', 'Binary mask', 'Label numbers', 'Probability', 'Layer bits']
AnatomicRegion = str  # Based on database field
VesselType = Literal['Artery', 'Vein', 'Vessel']

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

class ProjectBase(BaseModel):
    id: int
    name: str
    external: bool
    description: Optional[str] = None

class PatientBase(BaseModel):
    id: int
    identifier: str
    birth_date: Optional[datetime] = None
    sex: Optional[Sex] = None
    date_inserted: datetime

class StudyBase(BaseModel):
    id: int
    description: Optional[str] = None
    date: datetime
    study_instance_uid: str
    study_round: Optional[int] = None
    study_description: Optional[str] = None
    study_date: datetime
    date_inserted: datetime

class SeriesBase(BaseModel):
    id: int
    series_number: Optional[int] = None
    series_instance_uid: str

class InstanceBase(BaseModel):
    """Instance frontend object"""
    id: int
    
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

class OutputInstance(InstanceBase):
    project: ProjectBase
    patient: PatientBase
    study: StudyBase
    series: SeriesBase


class Annotation(BaseModel):
    id: int
    patient: Optional[Patient] = None
    study: Optional[Study] = None
    series: Optional[Series] = None
    instance: Optional[Instance] = None
    annotation_reference: Optional["Annotation"] = None
    creator: Creator
    feature: Feature
    interpretation: AnnotationTypeInterpretation  # Derived from annotation_type.interpretation
    created: Optional[datetime] = None

class FormSchema(BaseModel):
    """FormSchema frontend object"""
    id: int
    name: Optional[str] = None
    schema: Optional[Dict[str, Any]]

# === FORM ANNOTATION ===
class FormAnnotation(BaseModel):
    """FormAnnotation frontend object"""
    id: int
    form_schema: FormSchema
    patient: Patient
    study: Optional[Study] = None
    instance: Optional[Instance] = None
    creator: Creator
    sub_task: Optional["SubTask"] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    reference: Optional["FormAnnotation"] = None
    # value: ServerProperty - would need additional modeling


# === PROJECT ===
class Project(BaseModel):
    """Project frontend object"""
    id: int
    name: str

# === CREATOR ===
class Creator(BaseModel):
    """Creator frontend object"""
    id: int
    name: str
    msn: Optional[str] = None
    is_human: bool
    description: Optional[str] = None
    version: Optional[str] = None
    role: Optional[Any] = None

# === FEATURE ===
class Feature(BaseModel):
    """Feature frontend object"""
    id: int
    name: str

# === ANNOTATION TYPE ===
class AnnotationType(BaseModel):
    """AnnotationType frontend object"""
    id: int
    name: str
    interpretation: AnnotationTypeInterpretation

# === SCAN ===
class Scan(BaseModel):
    """Scan frontend object"""
    id: int
    mode: str

# === DEVICE MODEL ===
class DeviceModel(BaseModel):
    """DeviceModel frontend object"""
    id: int
    model: str

class Device(BaseModel):
    """Device frontend object"""
    id: int
    device_model: DeviceModel
    serialnumber: str
    description: Optional[str] = None
    model: str  # Derived property from device_model.model

class Patient(BaseModel):
    """Patient frontend object"""
    id: int
    identifier: str
    project: Project
    birth_date: Optional[datetime] = None
    sex: Optional[Sex] = None
    is_human: bool

class Study(BaseModel):
    """Study frontend object"""
    id: int
    patient: Patient
    description: Optional[str] = None
    date: datetime
    study_instance_uid: str

class Series(BaseModel):
    """Series frontend object"""
    id: int
    study: Study

# === INSTANCE ===





# === TAG ===
class Tag(BaseModel):
    """Tag frontend object"""
    id: int
    # Additional fields would need to be discovered

# === STUDY TAG ===
class StudyTag(BaseModel):
    """StudyTag frontend object"""
    id: str  # Composite: {StudyID}_{TagID}
    study: Study
    tag: Tag

# === INSTANCE TAG ===
class InstanceTag(BaseModel):
    """InstanceTag frontend object"""
    id: str  # Composite: {ImageInstanceID}_{TagID}
    instance: Instance
    tag: Tag

# === ANNOTATION TAG ===
class AnnotationTag(BaseModel):
    """AnnotationTag frontend object"""
    id: str  # Composite: {AnnotationID}_{TagID}
    annotation: Annotation
    tag: Tag

# === TASK DEFINITION ===
class TaskDefinition(BaseModel):
    """TaskDefinition frontend object"""
    id: int
    # Additional fields would need to be discovered

# === TASK STATE ===
class TaskState(BaseModel):
    """TaskState frontend object"""
    id: int
    # Additional fields would need to be discovered

class Task(BaseModel):
    """Task frontend object"""
    id: int
    # Additional fields would need to be discovered

# === SUB TASK ===
class SubTask(BaseModel):
    """SubTask frontend object"""
    id: int
    # Additional fields would need to be discovered

# === SUB TASK IMAGE LINK ===
class SubTaskImageLink(BaseModel):
    """SubTaskImageLink frontend object"""
    id: int
    # Additional fields would need to be discovered
