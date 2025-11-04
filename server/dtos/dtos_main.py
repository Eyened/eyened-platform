"""
Pydantic DTOs for EyeNed Platform
Auto-generated from TypeScript datamodel mappings

This file contains DTOs that represent:
1. Database field representations (with string field names as they appear in DB)
2. Frontend object representations (with property names as used in TypeScript)
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.image_instance import Laterality
from .dtos_aux import CreatorMeta, TagMeta
from pydantic import BaseModel

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= FEATURES =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FeatureBase(BaseModel):
    name: str


class SubFeatureItem(BaseModel):
    index: int
    name: str


class FeaturePUT(FeatureBase):
    subfeature_ids: List[int] | None = None


class FeaturePATCH(BaseModel):
    """Partial update for Feature with optional fields."""
    name: Optional[str] = None
    subfeature_ids: Optional[List[int]] = None


class FeatureGET(FeatureBase):
    id: int
    subfeatures: List[SubFeatureItem]
    subfeature_ids: List[int]
    date_inserted: datetime
    segmentation_count: Optional[int] = None

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= SEGMENTATIONS =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class SegmentationBase(BaseModel):
    image_instance_id: int
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
    
    feature_id: int
    subtask_id: Optional[int] = None

class SegmentationPATCH(BaseModel):
    reference_segmentation_id: Optional[int] = None
    feature_id: Optional[int] = None
    threshold: Optional[float] = None

class SegmentationGET(SegmentationBase):
    id: int
    annotation_type: Literal['grader_segmentation']
   
    feature: FeatureGET
    creator: CreatorMeta
    tags: List[TagMeta]

    date_inserted: datetime
    date_modified: Optional[datetime] = None


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= MODEL SEGMENTATIONS =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class ModelMeta(BaseModel):
    id: int
    name: str
    version: str

class ModelSegmentationGET(SegmentationBase):
    id: int
    annotation_type: Literal['model_segmentation']
   
    creator: ModelMeta
    feature: FeatureGET
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
    laterality: Optional[Laterality] = None
    sub_task_id: Optional[int] = None
    form_data: Optional[Any] = None
    form_annotation_reference_id: Optional[int] = None


class FormAnnotationPUT(FormAnnotationBase):
    pass


class FormAnnotationGET(FormAnnotationBase):
    id: int
    annotation_type: Literal['grader_form']

    object_type: Literal['patient', 'study', 'image_instance']
    tags: List[TagMeta]
    creator: CreatorMeta

    date_inserted: datetime
    date_modified: Optional[datetime] = None


class FormAnnotationPATCH(BaseModel):
    """Partial update for FormAnnotation with optional fields."""
    form_schema_id: Optional[int] = None
    patient_id: Optional[int] = None
    study_id: Optional[int] = None
    image_instance_id: Optional[int] = None
    laterality: Optional[Laterality] = None
    sub_task_id: Optional[int] = None
    form_data: Optional[Any] = None
    form_annotation_reference_id: Optional[int] = None


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= DEVICE MODELS =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class DeviceModelGET(BaseModel):
    id: int
    manufacturer: str
    model: str



