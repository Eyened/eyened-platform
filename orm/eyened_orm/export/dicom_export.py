from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import ImageInstance, Patient, Project, Series, Study


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


def normalize_pixel_array(arr: np.ndarray) -> tuple[np.ndarray, int, int, int]:
    arr = np.asarray(arr)
    if arr.ndim == 3 and arr.shape[-1] in (3, 4):
        arr = arr[..., :3]
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        return arr, 3, 8, 0

    if arr.dtype == np.uint8:
        return arr, 1, 8, 0
    if arr.dtype == np.uint16:
        return arr, 1, 16, 0

    arr = arr.astype(np.float32)
    arr_min = float(arr.min())
    arr_max = float(arr.max())
    if arr_max > arr_min:
        arr = (arr - arr_min) / (arr_max - arr_min)
    else:
        arr = np.zeros_like(arr)
    arr = (arr * 65535.0).astype(np.uint16)
    return arr, 1, 16, 0


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


def write_patient_keyfile(
    path: Path,
    patient_id_map: dict[str, str] | None = None,
    date_offset_map: dict[str, int] | None = None,
) -> None:
    patient_id_map = patient_id_map or {}
    date_offset_map = date_offset_map or {}
    all_patient_ids = sorted(set(patient_id_map) | set(date_offset_map))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
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
    filename_to_public_id: dict[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "exported_filename",
                "image_public_id",
            ]
        )
        for filename in sorted(filename_to_public_id):
            writer.writerow([filename, filename_to_public_id[filename]])


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
) -> tuple[
    dict[int, tuple[str, str]],
    dict[int, str],
    dict[int, str],
]:
    instance_registry: dict[int, tuple[str, str]] = {}
    series_registry: dict[int, str] = {}
    study_registry: dict[int, str] = {}

    for im in instances:
        sop_class_uid = im.SOPClassUid or SecondaryCaptureImageStorage
        sop_instance_uid = im.SOPInstanceUid or generate_uid()
        instance_registry[im.ImageInstanceID] = (str(sop_class_uid), str(sop_instance_uid))

        if im.SeriesID not in series_registry:
            series_registry[im.SeriesID] = str(im.Series.SeriesInstanceUid or generate_uid())

        study_id = im.Series.StudyID
        if study_id not in study_registry:
            study_registry[study_id] = str(im.Series.StudyInstanceUid or generate_uid())

    return instance_registry, series_registry, study_registry


def build_dicom_dataset(
    instance: ImageInstance,
    pixel_array: np.ndarray,
    sop_instance_uid: str,
    sop_class_uid: str,
    study_instance_uid: str,
    series_instance_uid: str,
    patient_id_value: str | None = None,
    date_offset_days: int = 0,
    localizer_refs: list[tuple[str, str]] | None = None,
) -> FileDataset:
    arr, samples_per_pixel, bits_allocated, pixel_representation = normalize_pixel_array(pixel_array)

    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(
        filename_or_obj="",
        dataset={},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )

    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = sop_instance_uid

    shifted_birth_date = shift_date_value(instance.Patient.BirthDate, date_offset_days)
    shifted_study_date = shift_date_value(instance.Study.StudyDate, date_offset_days)
    shifted_acq_dt = shift_datetime_value(instance.AcquisitionDateTime, date_offset_days)
    shifted_now = datetime.now() + timedelta(days=date_offset_days)

    ds.PatientID = patient_id_value or instance.Patient.PatientIdentifier or "UNKNOWN"
    ds.PatientSex = instance.Patient.Sex.value if instance.Patient.Sex else ""
    ds.PatientBirthDate = dt_to_dicom_date(shifted_birth_date)

    ds.StudyInstanceUID = study_instance_uid
    ds.SeriesInstanceUID = series_instance_uid

    ds.StudyDate = dt_to_dicom_date(shifted_study_date)
    ds.StudyTime = dt_to_dicom_time(shifted_acq_dt)
    ds.SeriesNumber = instance.Series.SeriesNumber or 1
    ds.InstanceNumber = 1

    ds.Modality = instance.DICOMModality.value if instance.DICOMModality else "OP"
    model = getattr(getattr(instance, "DeviceInstance", None), "DeviceModel", None)
    if model:
        ds.Manufacturer = model.Manufacturer
        ds.ManufacturerModelName = model.ManufacturerModelName

    ds.PhotometricInterpretation = (
        "RGB" if samples_per_pixel == 3 else (instance.PhotometricInterpretation or "MONOCHROME2")
    )
    ds.SamplesPerPixel = samples_per_pixel

    if arr.ndim == 2:
        rows, cols = arr.shape
    elif arr.ndim == 3 and samples_per_pixel == 3:
        rows, cols, _ = arr.shape
        ds.PlanarConfiguration = 0
    else:
        frames, rows, cols = arr.shape
        ds.NumberOfFrames = int(frames)

    ds.Rows = int(rows)
    ds.Columns = int(cols)
    ds.BitsAllocated = bits_allocated
    ds.BitsStored = bits_allocated
    ds.HighBit = bits_allocated - 1
    ds.PixelRepresentation = pixel_representation

    if localizer_refs:
        ds.ReferencedImageSequence = []
        for ref_sop_class_uid, ref_sop_instance_uid in localizer_refs:
            ref = Dataset()
            ref.ReferencedSOPClassUID = ref_sop_class_uid
            ref.ReferencedSOPInstanceUID = ref_sop_instance_uid
            ds.ReferencedImageSequence.append(ref)

    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.PixelData = arr.tobytes()
    ds.ContentDate = shifted_now.strftime("%Y%m%d")
    ds.ContentTime = shifted_now.strftime("%H%M%S")
    return ds


def export_instance_to_dicom(
    instance: ImageInstance,
    output_dir: Path,
    uid_registry: dict[int, tuple[str, str]],
    series_uid_registry: dict[int, str],
    study_uid_registry: dict[int, str],
    patient_id_map: dict[str, str] | None = None,
    patient_date_offset_map: dict[str, int] | None = None,
    filename_suffix: str | None = None,
    localizer_instances: list[ImageInstance] | None = None,
) -> Path:
    pixel_array = instance.pixel_array
    sop_class_uid, sop_instance_uid = uid_registry[instance.ImageInstanceID]

    source_patient_id = instance.Patient.PatientIdentifier or "UNKNOWN"
    patient_id_value = source_patient_id
    if patient_id_map:
        patient_id_value = patient_id_map.get(source_patient_id, patient_id_value)

    date_offset_days = 0
    if patient_date_offset_map:
        date_offset_days = patient_date_offset_map.get(source_patient_id, 0)

    localizer_refs: list[tuple[str, str]] = []
    if localizer_instances:
        for loc in localizer_instances:
            if loc.ImageInstanceID not in uid_registry:
                uid_registry[loc.ImageInstanceID] = (
                    str(loc.SOPClassUid or SecondaryCaptureImageStorage),
                    str(loc.SOPInstanceUid or generate_uid()),
                )
            localizer_refs.append(uid_registry[loc.ImageInstanceID])

    ds = build_dicom_dataset(
        instance,
        pixel_array,
        sop_instance_uid=sop_instance_uid,
        sop_class_uid=sop_class_uid,
        study_instance_uid=study_uid_registry[instance.Series.StudyID],
        series_instance_uid=series_uid_registry[instance.SeriesID],
        patient_id_value=patient_id_value,
        date_offset_days=date_offset_days,
        localizer_refs=localizer_refs,
    )

    shifted_study_date = shift_date_value(instance.Study.StudyDate, date_offset_days)
    suffix = filename_suffix or f"S{instance.ImageInstanceID:03d}"
    filename = build_export_filename(
        patient_id_value=patient_id_value,
        study_date_value=shifted_study_date,
        laterality_value=getattr(instance.Laterality, "value", None),
        suffix=suffix,
    )
    output_path = output_dir / filename
    ds.save_as(str(output_path), write_like_original=False)
    return output_path


def export_instances_to_dicom(
    session: Session,
    instances: list[ImageInstance],
    config: DicomExportConfig,
) -> DicomExportResult:
    config.output_dir.mkdir(parents=True, exist_ok=True)

    keyfile_path = config.keyfile_path or (config.output_dir / "patient_id_keyfile.csv")
    image_keyfile_path = config.image_keyfile_path or (
        config.output_dir / "image_filename_keyfile.csv"
    )
    exported_paths: list[Path] = []
    filename_to_public_id: dict[str, str] = {}
    query_instances = list(instances)


    series_ids = sorted({im.SeriesID for im in query_instances})
    if series_ids:
        stmt_series = select(ImageInstance).where(ImageInstance.SeriesID.in_(series_ids))
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
    uid_registry, series_uid_registry, study_uid_registry = build_uid_registry(instances_to_export)

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

    if config.pseudonymize_patient_ids or config.offset_dates_per_patient:
        write_patient_keyfile(
            keyfile_path,
            patient_id_map=patient_id_map,
            date_offset_map=patient_date_offset_map,
        )
    else:
        keyfile_path = None

    filename_suffix_map: dict[int, str] = {}
    group_counters: dict[tuple[str, str], int] = {}
    for im in instances_to_export:
        source_patient_id = im.Patient.PatientIdentifier or "UNKNOWN"
        patient_id_value = source_patient_id
        if patient_id_map:
            patient_id_value = patient_id_map.get(source_patient_id, patient_id_value)

        date_offset_days = 0
        if patient_date_offset_map:
            date_offset_days = patient_date_offset_map.get(source_patient_id, 0)

        shifted_study_date = shift_date_value(im.Study.StudyDate, date_offset_days)
        study_key = dt_to_dicom_date(shifted_study_date) or "UNKNOWNDATE"
        group_key = (patient_id_value, study_key)
        current = group_counters.get(group_key, 0) + 1
        group_counters[group_key] = current
        filename_suffix_map[im.ImageInstanceID] = f"S{current:03d}"

    for im in instances_to_export:
        source_patient_id = im.Patient.PatientIdentifier or "UNKNOWN"
        patient_id_value = source_patient_id
        if patient_id_map:
            patient_id_value = patient_id_map.get(source_patient_id, patient_id_value)

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
        )
        exported_paths.append(output_path)
        exported_key = str(output_path.relative_to(config.output_dir))
        filename_to_public_id[exported_key] = im.PublicID

    write_image_filename_keyfile(
        image_keyfile_path,
        filename_to_public_id=filename_to_public_id,
    )

    return DicomExportResult(
        exported_paths=exported_paths,
        keyfile_path=keyfile_path,
        image_keyfile_path=image_keyfile_path,
        requested_count=len(query_instances),
        exported_count=len(exported_paths),
    )
