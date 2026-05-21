from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from eyened_orm.image_instance import ETDRSField, Laterality, Modality, ModalityType
from eyened_orm.patient import SexEnum
from eyened_orm.project import ExternalEnum
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.task import SubTaskState, TaskState


class ContactImportFields(BaseModel):
    """Natural key / FK fields for the shared ``CONTACT`` importer entity (image and task graphs)."""

    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_institute: Optional[str] = None
    contact_orcid: Optional[str] = None


class InstancePOST(ContactImportFields):
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
    manufacturer: Optional[str] = Field(None, description="Manufacturer of the device")
    manufacturer_model_name: Optional[str] = Field(
        None, description="Model name of the device"
    )

    scan_mode: Optional[str] = Field(
        None,
        description="Scan.ScanMode; used with SCAN importer entity for lookup/create",
    )
    modality_tag: Optional[str] = Field(
        None,
        description="Modality.ModalityTag (lookup/create Modality table row); distinct from modality enum",
    )
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
    modality_id: Optional[int] = Field(
        None,
        description="Modality.ModalityID (SCAN-like PK for Modality table importer entity)",
    )
    scan_id: Optional[int] = Field(
        None,
        description="Scan.ScanID when referencing an existing Scan row",
    )

    slice_thickness: Optional[float] = Field(None, description="SliceThickness")
    alt_dataset_identifier: Optional[str] = Field(
        None, description="AltDatasetIdentifier"
    )
    
    # Note: these can be specified but should get the default values on import if not provided
    date_inserted: Optional[datetime] = Field(None, description="DateInserted")
    date_modified: Optional[datetime] = Field(None, description="DateModified")
    date_preprocessed: Optional[datetime] = Field(
        None, description="DatePreprocessed"
    )

    # Note these are added for completeness, but will be removed in a future release
    cf_roi: Optional[Dict[str, Any]] = Field(None, description="CFROI JSON")
    cf_keypoints: Optional[Dict[str, Any]] = Field(None, description="CFKeypoints JSON")
    cf_quality: Optional[float] = Field(None, description="CFQuality")


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

    # Scan entity: matched by scan_id or lookup Scan.ScanMode from scan_mode
    # Modality table entity: matched by modality_id or lookup Modality.ModalityTag from modality_tag

    # ImageInstance (matched by either image_instance_id, sop_instance_uid, or public_id)
    image_instance_id: Optional[int] = None
    public_id: Optional[str] = None
    inactive: Optional[bool] = None

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
    image_storage_hash: Optional[bytes] = Field(
        None, description="SHA-256 digest (32 bytes); maps to ImageStorage.Hash"
    )
    image_storage_checksum: Optional[str] = Field(
        None, description="Checksum string (e.g. MD5 hex); maps to ImageStorage.Checksum"
    )
    thumbnail_path: Optional[str] = Field(
        None,
        description="Thumbnail identifier under storage root; maps to ImageInstance.ThumbnailPath",
    )

    @model_validator(mode="after")
    def _validate_row(self) -> "ImportRow":
        # TODO: require fields depending on import mode (new upload vs patch-by-id, etc.)
        return self


class ImportTaskRow(ContactImportFields, BaseModel):
    """
    One flat record for the **task** importer graph (``TASK_ENTITY_SPECS``).

    ``ImageInstanceID`` on link rows is a plain FK (no ``ImageInstance`` entity in that graph).
    """

    model_config = ConfigDict(frozen=True)

    task_definition_id: Optional[int] = None
    task_definition_name: Optional[str] = None
    task_definition_config: Optional[Dict[str, Any]] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    task_description: Optional[str] = None
    task_state: TaskState = Field(
        default=TaskState.NotStarted,
        description="ORM Task.TaskState (Python enum; not a separate FK column)",
    )

    subtask_id: Optional[int] = None
    subtask_anonymous_identity: Optional[int] = Field(
        None,
        description="Batch-local key when creating an anonymous SubTask under the same Task",
    )
    subtask_comments: Optional[str] = None
    subtask_state: Optional[SubTaskState] = None

    image_instance_id: Optional[int] = Field(
        None,
        description="Target image for SubTaskImageLink (FK only; image row need not be imported in the same run)",
    )
    subtask_image_index: int = Field(
        0,
        description="SubTaskImageLink.ImageIndex",
    )
    subtask_image_link_id: Optional[int] = Field(
        None,
        description="Unused; composite link rows use natural lookup only",
    )

    creator_id: Optional[int] = None
    creator_name: Optional[str] = None
    creator_is_human: bool = Field(
        True,
        description="Used when the importer creates a new Creator from creator_name",
    )
    creator_employee_identifier: Optional[str] = None
    creator_description: Optional[str] = None


def expand_task_import_rows(
    shared: ImportTaskRow,
    image_groups: Sequence[Sequence[int]],
) -> list[ImportTaskRow]:
    """
    One **shared** task row plus a list of image-id **groups** → one :class:`ImportTaskRow`
    per image. Each group becomes one anonymous subtask; identities are ``1, 2, …`` in order.

    Example — two subtasks, first on ``[a, b, c]``, second on ``[a, d, e]``::

        expand_task_import_rows(
            ImportTaskRow(task_definition_name="td", task_name="t1", creator_name="c"),
            [[a, b, c], [a, d, e]],
        )
    """
    rows: list[ImportTaskRow] = []
    for anon, image_ids in enumerate(image_groups, start=1):
        for i, image_id in enumerate(image_ids):
            rows.append(
                shared.model_copy(
                    update={
                        "subtask_anonymous_identity": anon,
                        "image_instance_id": image_id,
                        "subtask_image_index": i,
                    }
                )
            )
    return rows


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
