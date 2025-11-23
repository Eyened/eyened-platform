from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from eyened_orm.image_instance import ETDRSField, Laterality, Modality, ModalityType
from eyened_orm.patient import SexEnum
from eyened_orm.segmentation import DataRepresentation, Datatype


class InstancePOST(BaseModel):
    sop_instance_uid: Optional[str] = None
    modality: Optional[Modality] = None
    dicom_modality: Optional[ModalityType] = None
    etdrs_field: Optional[ETDRSField] = None
    angio_graphy: Optional[str] = None
    laterality: Optional[Laterality] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    nr_of_frames: Optional[int] = None
    resolution_horizontal: Optional[float] = None
    resolution_vertical: Optional[float] = None
    resolution_axial: Optional[float] = None
    old_path: Optional[str] = None
    device_id: Optional[int] = None
    device_serial_number: Optional[str] = None
    device_description: Optional[str] = None
    device_manufacturer: Optional[str] = None
    device_model: Optional[str] = None


class SegmentationImport(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: np.ndarray

    # Segmentation properties (snake_case to match DTO style, will be mapped to PascalCase for ORM)
    data_type: Optional[Datatype] = None
    data_representation: Optional[DataRepresentation] = None
    depth: Optional[int] = None
    height: Optional[int] = None
    width: Optional[int] = None
    sparse_axis: Optional[int] = None
    image_projection_matrix: Optional[List[List[float]]] = None
    scan_indices: Optional[List[int]] = None
    threshold: Optional[float] = None
    reference_segmentation_id: Optional[int] = None


class ImageImport(InstancePOST):
    image: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    segmentations: List[SegmentationImport] = Field(default_factory=list)


class SeriesImport(BaseModel):
    series_id: Optional[str] = None
    images: List[ImageImport] = Field(default_factory=list)

    # Series properties
    series_number: Optional[int] = None
    series_instance_uid: Optional[str] = None


class StudyImport(BaseModel):
    study_date: Optional[date] = None
    series: List[SeriesImport] = Field(default_factory=list)

    # Study properties
    description: Optional[str] = None


class PatientImport(BaseModel):
    project_name: str
    patient_identifier: Optional[str] = None
    studies: List[StudyImport] = Field(default_factory=list)

    # Patient properties
    sex: Optional[SexEnum] = None
    birth_date: Optional[date] = None


class InstancePOSTFlat(InstancePOST):
    # Flattened version of PatientImport -> StudyImport -> SeriesImport -> ImageImport
    project_name: str = Field(..., description="Required project name")
    patient_identifier: Optional[str] = Field(None, description="Patient identifier")
    sex: Optional[SexEnum] = None
    birth_date: Optional[date] = None

    study_date: Optional[date] = None
    study_description: Optional[str] = None

    series_id: Optional[str] = None
    series_number: Optional[int] = None
    series_instance_uid: Optional[str] = None

    image: str = Field(..., description="Path to the image file")
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Optional key-value properties"
    )
