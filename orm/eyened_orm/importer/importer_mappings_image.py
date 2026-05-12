from __future__ import annotations

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
    ModalityTable,
    Scan,
)

from .importer_mappings_base import CONTACT, Entity, key, lookup, opt, req

PROJECT = Entity(
    model=Project,
    pk_column="ProjectID",
    pk_row_field="project_id",
    lookups=(lookup(key("ProjectName")),),
    anonymous_identity="project_name",  # this will make the importer create a new project using this name as fallback if not found
    implies=(opt(CONTACT, "Contact"),),
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
    implies=(req(PROJECT, "Project"),),
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
    implies=(req(PATIENT, "Patient"),),
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
    implies=(req(STUDY, "Study"),),
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
    implies=(req(DEVICE_MODEL, "DeviceModel"),),
    fields={
        "Description": "device_description",
        "SerialNumber": "device_serial_number",
    },
)

SCAN = Entity(
    model=Scan,
    pk_column="ScanID",
    pk_row_field="scan_id",
    lookups=(lookup(key("ScanMode")),),
    fields={
        "ScanMode": "scan_mode",
    },
)

MODALITY_TABLE = Entity(
    model=ModalityTable,
    pk_column="ModalityID",
    pk_row_field="modality_id",
    lookups=(lookup(key("ModalityTag")),),
    fields={
        "ModalityTag": "modality_tag",
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
        req(SERIES, "Series"),
        req(DEVICE_INSTANCE, "DeviceInstance"),
        opt(SCAN, "Scan"),
        opt(MODALITY_TABLE, "_Modality"),
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
        "SliceThickness": "slice_thickness",
        "ResolutionHorizontal": "resolution_horizontal",
        "ResolutionVertical": "resolution_vertical",
        "ResolutionAxial": "resolution_axial",
        "OldPath": "old_path",
        "DatasetIdentifier": "dataset_identifier",
        "AltDatasetIdentifier": "alt_dataset_identifier",
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
        "Inactive": "inactive",
        "ThumbnailPath": "thumbnail_path",
        "DateInserted": "date_inserted",
        "DateModified": "date_modified",
        "DatePreprocessed": "date_preprocessed",
        "CFROI": "cf_roi",
        "CFKeypoints": "cf_keypoints",
        "CFQuality": "cf_quality",
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
        req(STORAGE_BACKEND, "StorageBackend"),
        req(IMAGE_INSTANCE, "ImageInstance"),
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
    CONTACT,
    STORAGE_BACKEND,
    IMAGE_STORAGE,
    IMAGE_INSTANCE,
    SERIES,
    STUDY,
    PATIENT,
    PROJECT,
    DEVICE_INSTANCE,
    DEVICE_MODEL,
    SCAN,
    MODALITY_TABLE,
)
