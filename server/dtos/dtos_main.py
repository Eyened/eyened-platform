"""
Pydantic DTOs for EyeNed Platform
Auto-generated from TypeScript datamodel mappings

This file contains DTOs that represent:
1. Database field representations (with string field names as they appear in DB)
2. Frontend object representations (with property names as used in TypeScript)
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, get_origin

from eyened_orm.Segmentation import DataRepresentation, Datatype
from .dtos_aux import CreatorGET, CreatorMetadata, TagMeta
from .dtos_instances import InstanceGET, PatientGET, StudyGET
from pydantic import BaseModel

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= FEATURES =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FeatureBase(BaseModel):
    name: str


class FeaturePUT(FeatureBase):
    subfeature_ids: List[int] | None = None


class FeaturePATCH(BaseModel):
    """Partial update for Feature with optional fields."""
    name: Optional[str] = None
    subfeature_ids: Optional[List[int]] = None


class FeatureGET(FeatureBase):
    id: int
    subfeatures: List[str]
    subfeature_ids: List[int]
    date_inserted: datetime

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= SEGMENTATIONS =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class SegmentationBase(BaseModel):
    depth: int
    height: int
    width: int

    sparse_axis: Optional[int] = None
    image_projection_matrix: Optional[List[List[float]]] = None
    scan_indices: Optional[List[int]] = None
    threshold: Optional[float] = None
    reference_segmentation_id: Optional[int] = None

    data_type: Datatype
    data_representation: DataRepresentation

class SegmentationPUT(SegmentationBase):
    pass

class SegmentationPOST(SegmentationBase):
    image_instance_id: int
    feature_id: int
    creator_id: int

class SegmentationPATCH(BaseModel):
    reference_segmentation_id: Optional[int] = None
    feature_id: Optional[int] = None
    threshold: Optional[float] = None

class SegmentationGET(SegmentationBase):
    id: int
   
    feature: FeatureGET
    creator: CreatorMetadata
    tags: List[TagMeta]

    date_inserted: datetime
    date_modified: Optional[datetime] = None


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= FORM ANNOTATIONS =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


# === FORM SCHEMA ===
class FormSchemaBase(BaseModel):
    name: Optional[str] = None
    schema: Optional[Dict[str, Any]] = None


class FormSchemaPUT(FormSchemaBase):
    pass


class FormSchemaGET(FormSchemaBase):
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


class FormAnnotationPUT(FormAnnotationBase):
    pass


class FormAnnotationGET(FormAnnotationBase):
    id: int

    object_type: Literal['patient', 'study', 'image_instance']
    tags: List[TagMeta]

    date_inserted: datetime
    date_modified: Optional[datetime] = None


class FormAnnotationPATCH(BaseModel):
    """Partial update for FormAnnotation with optional fields."""
    form_schema_id: Optional[int] = None
    patient_id: Optional[int] = None
    study_id: Optional[int] = None
    image_instance_id: Optional[int] = None
    creator_id: Optional[int] = None
    sub_task_id: Optional[int] = None
    form_data: Optional[Dict[str, Any]] = None
    form_annotation_reference_id: Optional[int] = None


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= DEVICE MODELS =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class DeviceModelGET(BaseModel):
    id: int
    manufacturer: str
    model: str



