from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from eyened_orm.image_instance import ETDRSField, Laterality, Modality, ModalityType
from eyened_orm.patient import SexEnum
from eyened_orm.project import ExternalEnum
from eyened_orm.segmentation import DataRepresentation, Datatype


class InstancePOST(BaseModel):
    model_config = ConfigDict(frozen=True)

    sop_instance_uid: Optional[str] = None
    modality: Optional[Modality] = None
    dicom_modality: Optional[ModalityType] = None
    etdrs_field: Optional[ETDRSField] = None
    laterality: Optional[Laterality] = None
    height: Optional[int] = Field(None, description="Rows_y")
    width: Optional[int] = Field(None, description="Columns_x")
    depth: Optional[int] = Field(None, description="NrOfFrames")
    resolution_horizontal: Optional[float] = None
    resolution_vertical: Optional[float] = None
    resolution_axial: Optional[float] = None
    old_path: Optional[str] = None
    device_id: Optional[int] = None
    device_serial_number: Optional[str] = None
    device_description: Optional[str] = Field(
        None, description="Description of the device"
    )
    manufacturer: Optional[str] = Field(
        None, description="Manufacturer of the device"
    )
    manufacturer_model_name: Optional[str] = Field(
        None, description="Model name of the device"
    )

    scan_mode: Optional[str] = None
    source_info_id: Optional[int] = None
    anatomic_region: Optional[int] = None
    acquisition_date_time: Optional[datetime] = None
    angiography: Optional[str] = None
    samples_per_pixel: Optional[int] = None
    horizontal_field_of_view: Optional[float] = None
    sop_class_uid: Optional[str] = None
    photometric_interpretation: Optional[str] = None
    pupil_dilated: Optional[str] = None
    fda_identifier: Optional[str] = None

    dataset_identifier: Optional[str] = Field(
        None,
        description="Maps to ImageInstance.DatasetIdentifier, deprecated and will be removed in a future release",
    )
    modality_id: Optional[int] = None
    scan_id: Optional[int] = None


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

    # Metadata fields
    creator_name: Optional[str] = None
    feature_name: Optional[str] = None


class ImageImport(InstancePOST):
    object_key: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    segmentations: List[SegmentationImport] = Field(default_factory=list)


class SeriesImport(BaseModel):
    series_id: Optional[str] = None
    images: List[ImageImport] = Field(default_factory=list)

    # Series properties
    series_number: Optional[int] = None
    series_instance_uid: Optional[str] = None
    study_instance_uid: Optional[str] = None


class StudyImport(BaseModel):
    study_date: Optional[date] = None
    series: List[SeriesImport] = Field(default_factory=list)

    # Study properties
    description: Optional[str] = None


class PatientImport(BaseModel):
    project_name: str = Field(..., description="Name of the project")
    patient_identifier: str = Field(
        ..., description="Unique patient identifier within the project"
    )
    studies: List[StudyImport] = Field(default_factory=list)

    # Patient properties
    sex: Optional[SexEnum] = None
    birth_date: Optional[date] = None


class ImportRow(InstancePOST):
    """
    One flat record per image: project → patient → study → series → instance → storage fields.
    All fields are optional until consistency rules are enforced (see model validator).
    """

    # Project (matched by either project_id or project_name)
    project_id: Optional[int] = None
    project_name: Optional[str] = Field(None, description="Name of the project")
    # optional updates when create_projects or upsert
    project_description: Optional[str] = None
    project_doi: Optional[str] = None
    project_contact_id: Optional[int] = None
    project_external: Optional[ExternalEnum] = Field(
        None, description="Whether the project is external"
    )

    # Patient (matched by either patient_id or project and patient_identifier)
    patient_id: Optional[int] = None
    patient_identifier: Optional[str] = Field(
        None, description="Patient identifier (unique within the project)"
    )
    # optional updates when create_patients or upsert
    sex: Optional[SexEnum] = None
    birth_date: Optional[date] = Field(None, description="Patient's date of birth")

    # Study (matched by either study_id or patient and study_date)
    study_id: Optional[int] = None
    study_date: Optional[date] = Field(
        None, description="Date when the study was performed"
    )
    # optional updates when create_studies or upsert
    study_description: Optional[str] = None
    study_round: Optional[int] = None

    # Series (matched by either series_id or series_instance_uid)
    series_id: Optional[int] = None
    series_instance_uid: Optional[str] = Field(
        None, description="DICOM SeriesInstanceUID; stored on Series.SeriesInstanceUid"
    )

    # Batch-local grouping key for creating or reusing the same anonymous Series across multiple rows.
    # This can be used to create multiple ImageInstances for the same Series (even when series_instance_uid is absent).
    series_anonymous_identity: Optional[int] = Field(
        None, description="Batch-local grouping key for anonymous series creation"
    )
    # optional updates when create_series or upsert
    series_number: Optional[int] = None
    study_instance_uid: Optional[str] = Field(
        None, description="DICOM StudyInstanceUID; stored on Series.StudyInstanceUid"
    )

    # DeviceModel (matched by either device_model_id or manufacturer and manufacturer_model_name)
    device_model_id: Optional[int] = None

    # ImageInstance (matched by either image_instance_id or sop_instance_uid)
    image_instance_id: Optional[int] = None
    
    # Batch-local grouping key for creating or reusing the same anonymous ImageInstance across multiple rows.
    # This can be used to create multiple ImageStorages for the same ImageInstance (even when sop_instance_uid is absent).
    image_anonymous_identity: Optional[int] = Field(
        None,
        description="Batch-local grouping key for anonymous image instance creation",
    )

    # StorageBackend / ImageStorage
    # matched by either storage_backend_id or storage_backend_key,
    # and by either image_storage_id or storage_backend + object_key
    storage_backend_id: Optional[int] = None
    storage_backend_key: Optional[str] = Field(
        None, description="StorageBackend used for this image"
    )
    storage_backend_kind: Optional[str] = Field(
        None, description="Kind of the storage backend"
    )
    image_storage_id: Optional[int] = None
    object_key: Optional[str] = Field(
        None, description="Path to the image file within the storage backend"
    )

    image_storage_format: Optional[str] = Field(
        None, description="If set, overrides inferred Format for ImageStorage"
    )
    image_storage_is_primary: Optional[bool] = Field(
        None, description="If set, maps to ImageStorage.IsPrimary"
    )

    @model_validator(mode="after")
    def _validate_row(self) -> "ImportRow":
        # TODO: require fields depending on import mode (new upload vs patch-by-id, etc.)
        return self


# Backwards-compatible alias (API / notebooks)
InstancePOSTFlat = ImportRow


def import_rows_from_patients(patients: Sequence[PatientImport]) -> List[ImportRow]:
    """Expand nested PatientImport trees into one ImportRow per image."""
    rows: List[ImportRow] = []
    for p in patients:
        for st in p.studies:
            for se in st.series:
                for im in se.images:
                    im_dump = im.model_dump()
                    rows.append(
                        ImportRow(
                            project_name=p.project_name,
                            patient_identifier=p.patient_identifier,
                            sex=p.sex,
                            birth_date=p.birth_date,
                            study_date=st.study_date,
                            study_description=st.description,
                            series_id=se.series_id,
                            series_number=se.series_number,
                            series_instance_uid=se.series_instance_uid,
                            study_instance_uid=se.study_instance_uid,
                            **im_dump,
                        )
                    )
    return rows


def normalize_import_data(
    data: Sequence[Union[ImportRow, PatientImport]],
) -> List[ImportRow]:
    if not data:
        return []
    if isinstance(data[0], PatientImport):
        return import_rows_from_patients(data)  # type: ignore[arg-type]
    return [r if isinstance(r, ImportRow) else ImportRow.model_validate(r) for r in data]  # type: ignore[union-attr]


class ImportResult(BaseModel):
    """
    Result of an import that can be used for downstream steps and DB-only revert.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    import_run_id: str
    import_run: Any | None = None
