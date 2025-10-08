"""
Pydantic DTOs for EyeNed Platform
Auto-generated from TypeScript datamodel mappings

This file contains DTOs that represent:
1. Database field representations (with string field names as they appear in DB)
2. Frontend object representations (with property names as used in TypeScript)
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, get_origin

from pydantic import BaseModel, create_model, Field

from eyened_orm.image_instance import Laterality, ModalityType, Modality, ETDRSField
from eyened_orm.patient import SexEnum as Sex
from .dtos_main import FormAnnotationGET, ModelSegmentationGET, SegmentationGET
from .dtos_aux import TagMeta

# Type aliases matching TypeScript types
AnatomicRegion = str  # Based on database field


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= PROJECT, PATIENT, STUDY, SERIES =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ProjectGET(BaseModel):
    id: int
    name: str
    external: bool
    description: Optional[str] = None


class PatientGET(BaseModel):
    id: int
    identifier: str
    birth_date: Optional[date] = None
    sex: Optional[Sex] = None
    

class StudyGET(BaseModel):
    id: int
    description: Optional[str] = None
    date: datetime
    age: Optional[float] = None # patient age in years
    study_instance_uid: Optional[str] = None
    project: "ProjectMeta"
    patient: "PatientMeta"
    series: Optional[List["SeriesGET"]] = None
    tags: List[TagMeta]



class SeriesGET(BaseModel):
    id: int
    laterality: Optional[Laterality] = None
    series_number: Optional[int] = None
    series_instance_uid: str
    instance_ids: List[int] = Field(default_factory=list)



# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= INSTANCE METADATA =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class ProjectMeta(BaseModel):
    id: int
    name: str

class PatientMeta(BaseModel):
    id: int
    identifier: str
    birth_date: Optional[date] = None

class StudyMeta(BaseModel):
    id: int
    date: datetime

class SeriesMeta(BaseModel):
    id: int

class DeviceMeta(BaseModel):
    manufacturer: str
    model: str

class ScanMeta(BaseModel):
    mode: str


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= INSTANCES =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class InstanceBase(BaseModel):
    """Instance frontend object"""

    sop_instance_uid: str
    dataset_identifier: str
    thumbnail_identifier: str
    thumbnail_path: str
    modality: Optional[Modality] = None
    dicom_modality: Optional[ModalityType] = None
    etdrs_field: Optional[ETDRSField] = None
    angio_graphy: str
    laterality: Optional[Laterality] = None
    anatomic_region: AnatomicRegion
    rows: int
    columns: int
    nr_of_frames: int
    resolution_horizontal: float
    resolution_vertical: float
    resolution_axial: float
    cf_roi: Optional[Dict[str, Any]] = None
    cf_keypoints: Optional[Dict[str, Any]] = None
    cf_quality: Optional[float] = None
    date_inserted: datetime
    date_modified: Optional[datetime] = None
    date_preprocessed: Optional[datetime] = None


class InstanceMeta(BaseModel):
    id: int
    thumbnail_path: str
    modality: Optional[Modality] = None
    dicom_modality: Optional[ModalityType] = None
    etdrs_field: Optional[ETDRSField] = None
    laterality: Optional[Laterality] = None
    anatomic_region: AnatomicRegion
    device: DeviceMeta
    

class InstanceGET(InstanceBase):
    id: int
    project: ProjectMeta
    patient: PatientMeta
    study: StudyMeta
    series: SeriesMeta
    device: DeviceMeta
    scan: ScanMeta
    tags: List[TagMeta]

    segmentations: Optional[List[SegmentationGET]] = None
    model_segmentations: Optional[List[ModelSegmentationGET]] = None
    form_annotations: Optional[List[FormAnnotationGET]] = None

    date_inserted: datetime
    date_modified: Optional[datetime] = None
    date_preprocessed: Optional[datetime] = None



