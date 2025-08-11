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

from .dtos_aux import ROI, Keypoints

# Type aliases matching TypeScript types
Laterality = Literal["L", "R"]
Sex = Literal["M", "F"]
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
    study_instance_uid: Optional[str] = None



class SeriesGET(BaseModel):
    id: int
    series_number: Optional[int] = None
    series_instance_uid: str



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


class InstanceGET(InstanceBase):
    id: int
    project: ProjectMeta
    patient: PatientMeta
    study: StudyMeta
    series: SeriesMeta
    device: DeviceMeta
    scan: ScanMeta

    date_inserted: datetime
    date_modified: Optional[datetime] = None
    date_preprocessed: Optional[datetime] = None



