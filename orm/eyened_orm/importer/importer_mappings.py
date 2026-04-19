from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from eyened_orm.base import Base
from eyened_orm import (
    Project,
    Patient,
    Study,
    Series,
    StorageBackend,
    DeviceModel,
    DeviceInstance,
    ImageInstance,
    ImageStorage,
)


@dataclass(frozen=True, slots=True)
class LookupPart:
    column: str
    source: Entity | None


@dataclass(frozen=True, slots=True)
class Lookup:
    parts: tuple[LookupPart, ...]

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(part.column for part in self.parts)

    @property
    def tokens(self) -> tuple[Entity | None, ...]:
        return tuple(part.source for part in self.parts)


@dataclass(slots=True, eq=False)
class Entity:
    model: type[Base]
    pk_column: str
    pk_row_field: str
    lookups: tuple[Lookup, ...]
    fields: Mapping[str, str]
    non_mutable: frozenset[str] = frozenset()
    anonymous_identity: str | None = None
    implies: tuple[tuple[Entity, str], ...] = ()

    @property
    def lookup(self) -> Lookup:
        return self.lookups[0]

    @property
    def lookup_columns(self) -> tuple[str, ...]:
        return self.lookup.columns

    @property
    def lookup_tokens(self) -> tuple[str | Entity, ...]:
        return self.lookup.tokens

    @property
    def name(self) -> str:
        return self.model.__tablename__

    def __repr__(self) -> str:
        return f"Entity({self.name})"


def key(column: str, source: Entity | None = None) -> LookupPart:
    return LookupPart(column=column, source=source)


def lookup(*parts: LookupPart) -> Lookup:
    return Lookup(parts=parts)


PROJECT = Entity(
    model=Project,
    pk_column="ProjectID",
    pk_row_field="project_id",
    lookups=(lookup(key("ProjectName")),),
    anonymous_identity="project_name",  # this will make the importer create a new project using this name as fallback if not found
    fields={
        "ProjectName": "project_name",
        "External": "project_external",
        "Description": "project_description",
        "DOI": "project_doi",
        "ContactID": "project_contact_id",
    },
)

PATIENT = Entity(
    model=Patient,
    pk_column="PatientID",
    pk_row_field="patient_id",
    lookups=(
        lookup(
            key("ProjectID", PROJECT),
            key("PatientIdentifier"),
        ),
    ),
    implies=((PROJECT, "Project"),),
    fields={
        "PatientIdentifier": "patient_identifier",
        "Sex": "sex",
        "BirthDate": "birth_date",
    },
)

STUDY = Entity(
    model=Study,
    pk_column="StudyID",
    pk_row_field="study_id",
    lookups=(
        lookup(
            key("PatientID", PATIENT),
            key("StudyDate"),
        ),
    ),
    implies=((PATIENT, "Patient"),),
    fields={
        "StudyDate": "study_date",
        "StudyDescription": "study_description",
        "StudyRound": "study_round",
    },
)

SERIES = Entity(
    model=Series,
    pk_column="SeriesID",
    pk_row_field="series_id",
    lookups=(lookup(key("SeriesInstanceUid")),),
    anonymous_identity="series_anonymous_identity",
    implies=((STUDY, "Study"),),
    fields={
        "SeriesNumber": "series_number",
        "SeriesInstanceUid": "series_instance_uid",
        "StudyInstanceUid": "study_instance_uid",
    },
)

STORAGE_BACKEND = Entity(
    model=StorageBackend,
    pk_column="StorageBackendID",
    pk_row_field="storage_backend_id",
    lookups=(lookup(key("Key")),),
    fields={
        "Key": "storage_backend_key",
        "Kind": "storage_backend_kind",
    },
)

DEVICE_MODEL = Entity(
    model=DeviceModel,
    pk_column="DeviceModelID",
    pk_row_field="device_model_id",
    lookups=(
        lookup(
            key("Manufacturer"),
            key("ManufacturerModelName"),
        ),
    ),
    fields={
        "Manufacturer": "manufacturer",
        "ManufacturerModelName": "manufacturer_model_name",
    },
)

DEVICE_INSTANCE = Entity(
    model=DeviceInstance,
    pk_column="DeviceInstanceID",
    pk_row_field="device_id",
    lookups=(
        lookup(
            key("DeviceModelID", DEVICE_MODEL),
            key("Description"),
        ),
    ),
    implies=((DEVICE_MODEL, "DeviceModel"),),
    fields={
        "Description": "device_description",
        "SerialNumber": "device_serial_number",
    },
)

IMAGE_INSTANCE = Entity(
    model=ImageInstance,
    pk_column="ImageInstanceID",
    pk_row_field="image_instance_id",
    lookups=(
        lookup(key("SOPInstanceUid")),
        lookup(key("PublicID")),
    ),
    anonymous_identity="image_anonymous_identity",
    implies=(
        (SERIES, "Series"),
        (DEVICE_INSTANCE, "DeviceInstance"),
    ),
    fields={
        "SOPInstanceUid": "sop_instance_uid",
        "PublicID": "public_id",
        "Modality": "modality",
        "DICOMModality": "dicom_modality",
        "ETDRSField": "etdrs_field",
        "Laterality": "laterality",
        "Rows_y": "height",
        "Columns_x": "width",
        "NrOfFrames": "depth",
        "ResolutionHorizontal": "resolution_horizontal",
        "ResolutionVertical": "resolution_vertical",
        "ResolutionAxial": "resolution_axial",
        "OldPath": "old_path",
        "DatasetIdentifier": "dataset_identifier",
        "SourceInfoID": "source_info_id",
        "AnatomicRegion": "anatomic_region",
        "AcquisitionDateTime": "acquisition_date_time",
        "Angiography": "angiography",
        "SamplesPerPixel": "samples_per_pixel",
        "HorizontalFieldOfView": "horizontal_field_of_view",
        "SOPClassUid": "sop_class_uid",
        "PhotometricInterpretation": "photometric_interpretation",
        "PupilDilated": "pupil_dilated",
        "FDAIdentifier": "fda_identifier",
        "ModalityID": "modality_id",
        "ScanID": "scan_id",
        "Inactive": "inactive",
        "ThumbnailPath": "thumbnail_path",
    },
    non_mutable=frozenset({"PublicID"}),
)

IMAGE_STORAGE = Entity(
    model=ImageStorage,
    pk_column="ImageStorageID",
    pk_row_field="image_storage_id",
    lookups=(
        lookup(
            key("StorageBackendID", STORAGE_BACKEND),
            key("ObjectKey"),
        ),
    ),
    implies=(
        (STORAGE_BACKEND, "StorageBackend"),
        (IMAGE_INSTANCE, "ImageInstance"),
    ),
    fields={
        "ObjectKey": "object_key",
        "Format": "image_storage_format",
        "IsPrimary": "image_storage_is_primary",
        "Hash": "image_storage_hash",
        "Checksum": "image_storage_checksum",
    },
)

ENTITY_SPECS = (
    STORAGE_BACKEND,
    IMAGE_STORAGE,
    IMAGE_INSTANCE,
    SERIES,
    STUDY,
    PATIENT,
    PROJECT,
    DEVICE_INSTANCE,
    DEVICE_MODEL,
)
