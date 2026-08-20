from __future__ import annotations

import csv
import hashlib
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple, Optional

import numpy as np
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import (
    PYDICOM_IMPLEMENTATION_UID,
    ExplicitVRLittleEndian,
    MultiFrameGrayscaleByteSecondaryCaptureImageStorage,
    MultiFrameGrayscaleWordSecondaryCaptureImageStorage,
    MultiFrameTrueColorSecondaryCaptureImageStorage,
    SecondaryCaptureImageStorage,
    generate_uid,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import ImageInstance, Patient, Project, Series, Study

# v1 writes Secondary Capture for interchange, not a vendor OCT IOD.
# De-identification mints new Study/Series/SOP UIDs and keeps the patient
# keyfile outside the share directory.


@dataclass(slots=True)
class DicomExportConfig:
    output_dir: Path
    pseudonymize_patient_ids: bool = False
    pseudonym_salt: str = ""
    pseudonym_prefix: str = "PID"
    export_per_patient_subdir: bool = True
    offset_dates_per_patient: bool = False
    date_offset_salt: str = ""
    date_offset_min_days: int = -365
    date_offset_max_days: int = 365
    keyfile_path: Path | None = None
    image_keyfile_path: Path | None = None
    reuse_source_uids: bool = False
    include_inactive: bool = False


@dataclass(slots=True)
class DicomExportResult:
    exported_paths: list[Path]
    keyfile_path: Path | None
    image_keyfile_path: Path | None
    requested_count: int
    exported_count: int


def dt_to_dicom_date(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y%m%d")
    return ""


def dt_to_dicom_time(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H%M%S")
    return ""


class NormalizedPixels(NamedTuple):
    array: np.ndarray
    samples_per_pixel: int
    bits_allocated: int
    pixel_representation: int
    rescale_slope: float = 1.0
    rescale_intercept: float = 0.0


def normalize_pixel_array(arr: np.ndarray) -> NormalizedPixels:
    arr = np.asarray(arr)
    if arr.ndim >= 3 and arr.shape[-1] in (3, 4):
        arr = arr[..., :3]
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        return NormalizedPixels(arr, 3, 8, 0)

    if arr.dtype == np.uint8:
        return NormalizedPixels(arr, 1, 8, 0)
    if arr.dtype == np.uint16:
        return NormalizedPixels(arr, 1, 16, 0)

    arr = arr.astype(np.float32)
    arr_min = float(arr.min()) if arr.size else 0.0
    arr_max = float(arr.max()) if arr.size else 0.0
    if arr_max > arr_min:
        scaled = (arr - arr_min) / (arr_max - arr_min)
        slope = (arr_max - arr_min) / 65535.0
        intercept = arr_min
    else:
        scaled = np.zeros_like(arr)
        slope = 1.0
        intercept = arr_min
    return NormalizedPixels(
        (scaled * 65535.0).astype(np.uint16), 1, 16, 0, slope, intercept
    )


def select_secondary_capture_sop_class(
    arr: np.ndarray,
    samples_per_pixel: int,
    bits_allocated: int,
) -> str:
    if samples_per_pixel == 3 and arr.ndim == 4:
        return str(MultiFrameTrueColorSecondaryCaptureImageStorage)
    is_volume = arr.ndim == 3 and samples_per_pixel == 1
    if is_volume:
        if bits_allocated > 8:
            return str(MultiFrameGrayscaleWordSecondaryCaptureImageStorage)
        return str(MultiFrameGrayscaleByteSecondaryCaptureImageStorage)
    return str(SecondaryCaptureImageStorage)


def is_deidentifying(config: DicomExportConfig) -> bool:
    return config.pseudonymize_patient_ids or config.offset_dates_per_patient


def _is_path_inside(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def validate_export_config(config: DicomExportConfig) -> None:
    deidentifying = is_deidentifying(config)
    if config.offset_dates_per_patient and not config.pseudonymize_patient_ids:
        raise ValueError("offset_dates_per_patient requires pseudonymize_patient_ids")
    if config.reuse_source_uids and deidentifying:
        raise ValueError("reuse_source_uids cannot be combined with de-identification")
    if config.pseudonymize_patient_ids and not config.pseudonym_salt.strip():
        raise ValueError("pseudonym_salt is required when pseudonymize_patient_ids is enabled")
    if config.offset_dates_per_patient and not config.date_offset_salt.strip():
        raise ValueError("date_offset_salt is required when offset_dates_per_patient is enabled")
    if deidentifying and config.keyfile_path is None:
        raise ValueError(
            "keyfile_path is required when de-identifying; "
            "do not store the patient keyfile in output_dir"
        )
    if deidentifying and config.image_keyfile_path is None:
        raise ValueError(
            "image_keyfile_path is required when de-identifying; "
            "do not store the image keyfile in output_dir"
        )
    if config.keyfile_path is not None and _is_path_inside(
        config.keyfile_path, config.output_dir
    ):
        raise ValueError("patient keyfile_path must be outside output_dir")
    if config.image_keyfile_path is not None and _is_path_inside(
        config.image_keyfile_path, config.output_dir
    ):
        raise ValueError("image_keyfile_path must be outside output_dir")


def pseudonymize_patient_identifier(
    patient_identifier: str | None,
    salt: str,
    prefix: str = "PID",
) -> str:
    source = (patient_identifier or "UNKNOWN").strip()
    digest = hashlib.sha256(f"{salt}|{source}".encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}{digest}"


def build_patient_id_map(
    instances: list[ImageInstance],
    salt: str,
    prefix: str = "PID",
) -> dict[str, str]:
    unique_ids = sorted({(im.Patient.PatientIdentifier or "UNKNOWN") for im in instances})
    return {
        original: pseudonymize_patient_identifier(original, salt=salt, prefix=prefix)
        for original in unique_ids
    }


def patient_date_offset_days(
    patient_identifier: str | None,
    salt: str,
    min_days: int,
    max_days: int,
) -> int:
    if min_days > max_days:
        raise ValueError("date_offset_min_days must be <= date_offset_max_days")
    source = (patient_identifier or "UNKNOWN").strip()
    digest = hashlib.sha256(f"{salt}|{source}".encode("utf-8")).hexdigest()
    raw_value = int(digest[:12], 16)
    span = max_days - min_days + 1
    return min_days + (raw_value % span)


def build_patient_date_offset_map(
    instances: list[ImageInstance],
    salt: str,
    min_days: int,
    max_days: int,
) -> dict[str, int]:
    unique_ids = sorted({(im.Patient.PatientIdentifier or "UNKNOWN") for im in instances})
    return {
        original: patient_date_offset_days(
            original,
            salt=salt,
            min_days=min_days,
            max_days=max_days,
        )
        for original in unique_ids
    }


def _open_restricted_csv(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    return os.fdopen(fd, "w", newline="", encoding="utf-8")


def write_patient_keyfile(
    path: Path,
    patient_id_map: dict[str, str] | None = None,
    date_offset_map: dict[str, int] | None = None,
) -> None:
    patient_id_map = patient_id_map or {}
    date_offset_map = date_offset_map or {}
    all_patient_ids = sorted(set(patient_id_map) | set(date_offset_map))

    with _open_restricted_csv(path) as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "original_patient_id",
                "pseudonymized_patient_id",
                "date_offset_days",
            ]
        )
        for original in all_patient_ids:
            writer.writerow(
                [
                    original,
                    patient_id_map.get(original, ""),
                    date_offset_map.get(original, ""),
                ]
            )


def write_image_filename_keyfile(
    path: Path,
    rows: list[tuple[str, str, str, str, str]],
) -> None:
    with _open_restricted_csv(path) as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "exported_filename",
                "image_public_id",
                "sop_instance_uid",
                "series_instance_uid",
                "study_instance_uid",
            ]
        )
        for row in sorted(rows, key=lambda item: item[0]):
            writer.writerow(row)


def shift_date_value(value: date | None, offset_days: int) -> date | None:
    if value is None:
        return None
    return value + timedelta(days=offset_days)


def shift_datetime_value(value: datetime | None, offset_days: int) -> datetime | None:
    if value is None:
        return None
    return value + timedelta(days=offset_days)


def safe_filename_component(value: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    cleaned = "".join(ch if ch in allowed else "_" for ch in value)
    return cleaned.strip("_") or "UNKNOWN"


def build_export_filename(
    patient_id_value: str,
    study_date_value: date | None,
    laterality_value: str | None,
    suffix: str,
) -> str:
    patient_part = safe_filename_component(patient_id_value)
    study_part = dt_to_dicom_date(study_date_value) or "UNKNOWNDATE"
    laterality_part = safe_filename_component(laterality_value or "U")
    suffix_part = safe_filename_component(suffix)
    return f"{patient_part}_{study_part}_{laterality_part}_{suffix_part}.dcm"


def is_oct_volume(instance: ImageInstance) -> bool:
    modality_name = getattr(instance.Modality, "value", str(instance.Modality or ""))
    return bool(instance.NrOfFrames and instance.NrOfFrames > 1) and "OCT" in modality_name.upper()


def get_storage_directory(instance: ImageInstance) -> str | None:
    storage = instance.primary_storage
    if not storage or not storage.ObjectKey:
        return None
    parts = storage.ObjectKey.rsplit("/", 1)
    if len(parts) != 2:
        return ""
    return parts[0]


def is_likely_localizer_candidate(candidate: ImageInstance) -> bool:
    if candidate.NrOfFrames and candidate.NrOfFrames > 1:
        return False
    dicom_modality = getattr(candidate.DICOMModality, "value", "")
    modality_name = getattr(candidate.Modality, "value", str(candidate.Modality or ""))
    modality_upper = modality_name.upper()
    return bool(
        dicom_modality == "OP"
        or "INFRARED" in modality_upper
        or "SLO" in modality_upper
        or "FUNDUS" in modality_upper
    )


def pick_series_localizers(
    oct_instance: ImageInstance,
    series_instances: list[ImageInstance],
) -> list[ImageInstance]:
    oct_dir = get_storage_directory(oct_instance)
    path_matched: list[ImageInstance] = []
    heuristic_fallback: list[ImageInstance] = []

    for candidate in series_instances:
        if candidate.ImageInstanceID == oct_instance.ImageInstanceID:
            continue
        if not is_likely_localizer_candidate(candidate):
            continue

        cand_dir = get_storage_directory(candidate)
        if oct_dir is not None and cand_dir == oct_dir:
            path_matched.append(candidate)
        else:
            heuristic_fallback.append(candidate)

    chosen = path_matched if path_matched else heuristic_fallback
    chosen.sort(key=lambda x: x.ImageInstanceID)
    return chosen


def fetch_instances_for_export(
    session: Session,
    project_name: str,
    patient_identifier: str | None = None,
    limit: int = 20,
    include_inactive: bool = False,
) -> list[ImageInstance]:
    stmt = (
        select(ImageInstance)
        .join(Series)
        .join(Study)
        .join(Patient)
        .join(Project)
        .where(Project.ProjectName == project_name)
        .order_by(ImageInstance.ImageInstanceID.asc())
        .limit(limit)
    )
    if not include_inactive:
        stmt = stmt.where(~ImageInstance.Inactive)
    if patient_identifier:
        stmt = stmt.where(Patient.PatientIdentifier == patient_identifier)
    return session.scalars(stmt).all()


def build_uid_registry(
    instances: list[ImageInstance],
    *,
    reuse_source_uids: bool = False,
) -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
    instance_registry: dict[int, str] = {}
    series_registry: dict[int, str] = {}
    study_registry: dict[int, str] = {}

    for im in instances:
        source_sop = im.SOPInstanceUid if reuse_source_uids else None
        instance_registry[im.ImageInstanceID] = str(source_sop or generate_uid())

        if im.SeriesID not in series_registry:
            source_series = im.Series.SeriesInstanceUid if reuse_source_uids else None
            series_registry[im.SeriesID] = str(source_series or generate_uid())

        study_id = im.Series.StudyID
        if study_id not in study_registry:
            source_study = im.Series.StudyInstanceUid if reuse_source_uids else None
            study_registry[study_id] = str(source_study or generate_uid())

    return instance_registry, series_registry, study_registry


def build_study_datetime_map(
    instances: list[ImageInstance],
    patient_date_offset_map: dict[str, int] | None = None,
) -> dict[int, tuple[date | None, datetime | None]]:
    grouped: dict[int, list[ImageInstance]] = {}
    for im in instances:
        grouped.setdefault(im.Series.StudyID, []).append(im)

    result: dict[int, tuple[date | None, datetime | None]] = {}
    for study_id, members in grouped.items():
        source_patient_id = members[0].Patient.PatientIdentifier or "UNKNOWN"
        offset_days = 0
        if patient_date_offset_map is not None:
            offset_days = _require_mapped(
                patient_date_offset_map, source_patient_id, "date offset"
            )

        study_date = shift_date_value(members[0].Study.StudyDate, offset_days)
        acquisition_times = [
            im.AcquisitionDateTime for im in members if im.AcquisitionDateTime is not None
        ]
        study_time_src = min(acquisition_times) if acquisition_times else None
        study_time = shift_datetime_value(study_time_src, offset_days)
        result[study_id] = (study_date, study_time)
    return result


def build_instance_number_map(instances: list[ImageInstance]) -> dict[int, int]:
    grouped: dict[int, list[ImageInstance]] = {}
    for im in instances:
        grouped.setdefault(im.SeriesID, []).append(im)

    result: dict[int, int] = {}
    for members in grouped.values():
        ordered = sorted(members, key=lambda x: x.ImageInstanceID)
        for index, im in enumerate(ordered, start=1):
            result[im.ImageInstanceID] = index
    return result


def _require_mapped(mapping: dict, key, label: str):
    if key not in mapping:
        raise KeyError(f"missing {label} for {key!r}")
    return mapping[key]


def _resolved_patient_id(
    instance: ImageInstance,
    patient_id_map: dict[str, str] | None,
) -> tuple[str, str]:
    source_patient_id = instance.Patient.PatientIdentifier or "UNKNOWN"
    if patient_id_map is None:
        return source_patient_id, source_patient_id
    return source_patient_id, _require_mapped(patient_id_map, source_patient_id, "pseudonym")


def series_description_for_instance(instance: ImageInstance) -> str:
    parts: list[str] = []
    scan = getattr(instance, "Scan", None)
    scan_mode = getattr(scan, "ScanMode", None)
    if scan_mode:
        parts.append(str(scan_mode))
    elif instance.Modality:
        parts.append(getattr(instance.Modality, "value", str(instance.Modality)))
    etdrs = getattr(instance.ETDRSField, "value", None)
    if etdrs:
        parts.append(str(etdrs))
    anatomic = instance.AnatomicRegion
    if anatomic == 1:
        parts.append("OpticDisc")
    elif anatomic == 2:
        parts.append("Macula")
    return " ".join(parts)


def pixel_spacing_mm(
    instance: ImageInstance, *, is_volume: bool
) -> tuple[float, float] | None:
    """Row/column spacing in millimetres, matching ImageInstance axis conventions."""
    if is_volume:
        row_mm = instance.ResolutionAxial
        col_mm = instance.ResolutionHorizontal
    else:
        row_mm = instance.ResolutionVertical
        col_mm = instance.ResolutionHorizontal
    if row_mm is None or col_mm is None:
        return None
    return float(row_mm), float(col_mm)


def apply_optional_instance_metadata(
    ds: Dataset,
    instance: ImageInstance,
    *,
    is_volume: bool,
    date_offset_days: int = 0,
    deidentify: bool = False,
) -> None:
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.ImageType = ["DERIVED", "SECONDARY"]
    ds.AccessionNumber = ""
    ds.PatientName = ds.get("PatientName", "")

    description = series_description_for_instance(instance)
    if description:
        ds.SeriesDescription = description

    laterality = getattr(instance.Laterality, "value", None)
    if laterality:
        ds.Laterality = laterality

    shifted_acq = shift_datetime_value(instance.AcquisitionDateTime, date_offset_days)
    if shifted_acq is not None:
        ds.AcquisitionDate = dt_to_dicom_date(shifted_acq)
        ds.AcquisitionTime = dt_to_dicom_time(shifted_acq)

    spacing = pixel_spacing_mm(instance, is_volume=is_volume)
    if spacing is not None:
        ds.PixelSpacing = [spacing[0], spacing[1]]

    slice_thickness = instance.SliceThickness
    if slice_thickness is None and is_volume:
        slice_thickness = instance.ResolutionVertical
    if slice_thickness is not None:
        ds.SliceThickness = float(slice_thickness)
    if is_volume and instance.ResolutionVertical is not None:
        ds.SpacingBetweenSlices = float(instance.ResolutionVertical)

    if instance.HorizontalFieldOfView is not None:
        ds.HorizontalFieldOfView = float(instance.HorizontalFieldOfView)

    if instance.PupilDilated is not None:
        ds.PupilDilated = "YES" if instance.PupilDilated else "NO"

    device = getattr(instance, "DeviceInstance", None)
    serial = getattr(device, "SerialNumber", None)
    if serial and not deidentify:
        ds.DeviceSerialNumber = serial

    if deidentify:
        ds.PatientIdentityRemoved = "YES"
        ds.DeidentificationMethod = (
            "Patient IDs hashed; dates offset; UIDs replaced"
        )


def build_dicom_dataset(
    instance: ImageInstance,
    pixel_array: np.ndarray,
    sop_instance_uid: str,
    study_instance_uid: str,
    series_instance_uid: str,
    patient_id_value: str | None = None,
    date_offset_days: int = 0,
    localizer_refs: list[tuple[str, str]] | None = None,
    instance_number: int = 1,
    study_date: date | None = None,
    study_time: datetime | None = None,
    deidentify: bool = False,
) -> FileDataset:
    normalized = normalize_pixel_array(pixel_array)
    arr = normalized.array
    samples_per_pixel = normalized.samples_per_pixel
    bits_allocated = normalized.bits_allocated
    pixel_representation = normalized.pixel_representation
    sop_class_uid = select_secondary_capture_sop_class(
        arr, samples_per_pixel, bits_allocated
    )

    file_meta = FileMetaDataset()
    file_meta.FileMetaInformationVersion = b"\x00\x01"
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

    ds = FileDataset(
        filename_or_obj="",
        dataset={},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )

    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = sop_instance_uid
    ds.ConversionType = "WSD"
    ds.PatientName = ""

    if study_date is None:
        study_date = shift_date_value(instance.Study.StudyDate, date_offset_days)
    if study_time is None:
        study_time = shift_datetime_value(instance.AcquisitionDateTime, date_offset_days)

    ds.PatientID = patient_id_value or instance.Patient.PatientIdentifier or "UNKNOWN"
    ds.PatientSex = instance.Patient.Sex.value if instance.Patient.Sex else ""
    if deidentify:
        ds.PatientBirthDate = ""
    else:
        ds.PatientBirthDate = dt_to_dicom_date(instance.Patient.BirthDate)

    ds.StudyInstanceUID = study_instance_uid
    ds.SeriesInstanceUID = series_instance_uid

    ds.StudyDate = dt_to_dicom_date(study_date)
    ds.StudyTime = dt_to_dicom_time(study_time)
    ds.SeriesNumber = instance.Series.SeriesNumber or 1
    ds.InstanceNumber = int(instance_number)

    laterality = getattr(instance.Laterality, "value", None)
    if laterality:
        ds.ImageLaterality = laterality

    ds.Modality = instance.DICOMModality.value if instance.DICOMModality else "OP"
    model = getattr(getattr(instance, "DeviceInstance", None), "DeviceModel", None)
    if model:
        ds.Manufacturer = model.Manufacturer
        ds.ManufacturerModelName = model.ManufacturerModelName

    ds.PhotometricInterpretation = "RGB" if samples_per_pixel == 3 else "MONOCHROME2"
    ds.SamplesPerPixel = samples_per_pixel
    ds.BurnedInAnnotation = "YES"

    if samples_per_pixel == 3 and arr.ndim == 4:
        frames, rows, cols, _ = arr.shape
        ds.NumberOfFrames = int(frames)
        ds.PlanarConfiguration = 0
        is_volume = False
    elif arr.ndim == 2:
        rows, cols = arr.shape
        is_volume = False
    elif arr.ndim == 3 and samples_per_pixel == 3:
        rows, cols, _ = arr.shape
        ds.PlanarConfiguration = 0
        is_volume = False
    elif arr.ndim == 3:
        frames, rows, cols = arr.shape
        ds.NumberOfFrames = int(frames)
        is_volume = True
    else:
        raise ValueError(f"unsupported pixel array shape {arr.shape}")

    apply_optional_instance_metadata(
        ds,
        instance,
        is_volume=is_volume,
        date_offset_days=date_offset_days,
        deidentify=deidentify,
    )

    ds.Rows = int(rows)
    ds.Columns = int(cols)
    ds.BitsAllocated = bits_allocated
    ds.BitsStored = bits_allocated
    ds.HighBit = bits_allocated - 1
    ds.PixelRepresentation = pixel_representation

    if samples_per_pixel == 1:
        ds.RescaleIntercept = float(normalized.rescale_intercept)
        ds.RescaleSlope = float(normalized.rescale_slope)
        ds.RescaleType = "US"
        ds.PresentationLUTShape = "IDENTITY"

    if getattr(ds, "NumberOfFrames", None):
        ds.FrameTime = 0.0
        ds.FrameIncrementPointer = ds["FrameTime"].tag

    if localizer_refs:
        ds.ReferencedImageSequence = []
        for ref_sop_class_uid, ref_sop_instance_uid in localizer_refs:
            ref = Dataset()
            ref.ReferencedSOPClassUID = ref_sop_class_uid
            ref.ReferencedSOPInstanceUID = ref_sop_instance_uid
            ds.ReferencedImageSequence.append(ref)

    ds.PixelData = arr.tobytes()
    now = datetime.now()
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S")
    return ds


def export_instance_to_dicom(
    instance: ImageInstance,
    output_dir: Path,
    uid_registry: dict[int, str],
    series_uid_registry: dict[int, str],
    study_uid_registry: dict[int, str],
    patient_id_map: dict[str, str] | None = None,
    patient_date_offset_map: dict[str, int] | None = None,
    filename_suffix: str | None = None,
    localizer_instances: list[ImageInstance] | None = None,
    instance_number: int = 1,
    study_date: date | None = None,
    study_time: datetime | None = None,
    deidentify: bool = False,
    reuse_source_uids: bool = False,
) -> Path:
    pixel_array = instance.pixel_array
    sop_instance_uid = uid_registry[instance.ImageInstanceID]

    _, patient_id_value = _resolved_patient_id(instance, patient_id_map)

    date_offset_days = 0
    if patient_date_offset_map is not None:
        source_patient_id = instance.Patient.PatientIdentifier or "UNKNOWN"
        date_offset_days = _require_mapped(
            patient_date_offset_map, source_patient_id, "date offset"
        )

    localizer_refs: list[tuple[str, str]] = []
    if localizer_instances:
        for loc in localizer_instances:
            if loc.ImageInstanceID not in uid_registry:
                source_sop = loc.SOPInstanceUid if reuse_source_uids else None
                uid_registry[loc.ImageInstanceID] = str(source_sop or generate_uid())
            localizer_refs.append(
                (str(SecondaryCaptureImageStorage), uid_registry[loc.ImageInstanceID])
            )

    ds = build_dicom_dataset(
        instance,
        pixel_array,
        sop_instance_uid=sop_instance_uid,
        study_instance_uid=study_uid_registry[instance.Series.StudyID],
        series_instance_uid=series_uid_registry[instance.SeriesID],
        patient_id_value=patient_id_value,
        date_offset_days=date_offset_days,
        localizer_refs=localizer_refs,
        instance_number=instance_number,
        study_date=study_date,
        study_time=study_time,
        deidentify=deidentify,
    )

    if study_date is None:
        study_date = shift_date_value(instance.Study.StudyDate, date_offset_days)
    suffix = filename_suffix or f"S{instance.ImageInstanceID:03d}"
    filename = build_export_filename(
        patient_id_value=patient_id_value,
        study_date_value=study_date,
        laterality_value=getattr(instance.Laterality, "value", None),
        suffix=suffix,
    )
    output_path = output_dir / filename
    ds.save_as(str(output_path), enforce_file_format=True)
    return output_path


def export_instances_to_dicom(
    session: Session,
    instances: list[ImageInstance],
    config: DicomExportConfig,
) -> DicomExportResult:
    validate_export_config(config)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    deidentifying = is_deidentifying(config)
    keyfile_path = config.keyfile_path
    image_keyfile_path = config.image_keyfile_path
    if image_keyfile_path is None:
        image_keyfile_path = config.output_dir.resolve().parent / "image_filename_keyfile.csv"
        if _is_path_inside(image_keyfile_path, config.output_dir):
            raise ValueError("image_keyfile_path must be outside output_dir")
    exported_paths: list[Path] = []
    image_keyfile_rows: list[tuple[str, str, str, str, str]] = []
    query_instances = list(instances)

    series_ids = sorted({im.SeriesID for im in query_instances})
    if series_ids:
        stmt_series = select(ImageInstance).where(ImageInstance.SeriesID.in_(series_ids))
        if not config.include_inactive:
            stmt_series = stmt_series.where(~ImageInstance.Inactive)
        all_series_instances = session.scalars(stmt_series).all()
    else:
        all_series_instances = list(query_instances)

    by_series: dict[int, list[ImageInstance]] = {}
    by_id: dict[int, ImageInstance] = {}
    for im in all_series_instances:
        by_series.setdefault(im.SeriesID, []).append(im)
        by_id[im.ImageInstanceID] = im
    for im in query_instances:
        if im.ImageInstanceID not in by_id:
            by_series.setdefault(im.SeriesID, []).append(im)
            by_id[im.ImageInstanceID] = im

    instances_to_export_ids = {im.ImageInstanceID for im in query_instances}
    localizer_map: dict[int, list[ImageInstance]] = {}
    for im in query_instances:
        if not is_oct_volume(im):
            continue
        localizers = pick_series_localizers(im, by_series.get(im.SeriesID, []))
        localizer_map[im.ImageInstanceID] = localizers
        for loc in localizers:
            instances_to_export_ids.add(loc.ImageInstanceID)

    instances_to_export = [by_id[iid] for iid in sorted(instances_to_export_ids) if iid in by_id]
    uid_registry, series_uid_registry, study_uid_registry = build_uid_registry(
        instances_to_export,
        reuse_source_uids=config.reuse_source_uids,
    )

    patient_id_map: Optional[dict[str, str]] = None
    if config.pseudonymize_patient_ids:
        patient_id_map = build_patient_id_map(
            instances_to_export,
            salt=config.pseudonym_salt,
            prefix=config.pseudonym_prefix,
        )

    patient_date_offset_map: Optional[dict[str, int]] = None
    if config.offset_dates_per_patient:
        patient_date_offset_map = build_patient_date_offset_map(
            instances_to_export,
            salt=config.date_offset_salt,
            min_days=config.date_offset_min_days,
            max_days=config.date_offset_max_days,
        )

    if deidentifying:
        if keyfile_path is None:
            raise ValueError("keyfile_path is required when de-identifying")
        write_patient_keyfile(
            keyfile_path,
            patient_id_map=patient_id_map,
            date_offset_map=patient_date_offset_map,
        )

    study_datetime_map = build_study_datetime_map(
        instances_to_export,
        patient_date_offset_map=patient_date_offset_map,
    )
    instance_number_map = build_instance_number_map(instances_to_export)

    filename_suffix_map: dict[int, str] = {}
    group_counters: dict[tuple[str, str], int] = {}
    for im in instances_to_export:
        _, patient_id_value = _resolved_patient_id(im, patient_id_map)
        study_date, _ = study_datetime_map[im.Series.StudyID]
        study_key = dt_to_dicom_date(study_date) or "UNKNOWNDATE"
        group_key = (patient_id_value, study_key)
        current = group_counters.get(group_key, 0) + 1
        group_counters[group_key] = current
        filename_suffix_map[im.ImageInstanceID] = f"S{current:03d}"

    try:
        for im in instances_to_export:
            _, patient_id_value = _resolved_patient_id(im, patient_id_map)
            study_date, study_time = study_datetime_map[im.Series.StudyID]

            target_output_dir = config.output_dir
            if config.export_per_patient_subdir:
                patient_dirname = safe_filename_component(patient_id_value)
                target_output_dir = config.output_dir / patient_dirname
                target_output_dir.mkdir(parents=True, exist_ok=True)

            localizers = localizer_map.get(im.ImageInstanceID, [])
            output_path = export_instance_to_dicom(
                im,
                target_output_dir,
                uid_registry=uid_registry,
                series_uid_registry=series_uid_registry,
                study_uid_registry=study_uid_registry,
                patient_id_map=patient_id_map,
                patient_date_offset_map=patient_date_offset_map,
                filename_suffix=filename_suffix_map.get(im.ImageInstanceID),
                localizer_instances=localizers,
                instance_number=instance_number_map.get(im.ImageInstanceID, 1),
                study_date=study_date,
                study_time=study_time,
                deidentify=deidentifying,
                reuse_source_uids=config.reuse_source_uids,
            )
            exported_paths.append(output_path)
            exported_key = str(output_path.relative_to(config.output_dir))
            image_keyfile_rows.append(
                (
                    exported_key,
                    im.PublicID,
                    uid_registry[im.ImageInstanceID],
                    series_uid_registry[im.SeriesID],
                    study_uid_registry[im.Series.StudyID],
                )
            )
    finally:
        write_image_filename_keyfile(
            image_keyfile_path,
            rows=image_keyfile_rows,
        )

    return DicomExportResult(
        exported_paths=exported_paths,
        keyfile_path=keyfile_path if deidentifying else None,
        image_keyfile_path=image_keyfile_path,
        requested_count=len(query_instances),
        exported_count=len(exported_paths),
    )
