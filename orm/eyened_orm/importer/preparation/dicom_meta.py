from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

import pydicom
from pydicom.valuerep import DA, TM

from eyened_orm.image_instance import Laterality, Modality, ModalityType

# Keys used for OCT–enface linking; stripped before ImportRow validation.
LINK_META_KEYS = frozenset(
    {
        "frame_of_reference_uid",
        "referenced_sop_instance_uids",
    }
)


def _str_or_none(val: Any) -> str | None:
    if val is None or val == "":
        return None
    return str(val)


def _laterality(val: Any) -> Laterality | None:
    s = _str_or_none(val)
    if not s:
        return None
    s = s.strip().upper()[:1]
    if s == "L":
        return Laterality.L
    if s == "R":
        return Laterality.R
    return None


def _dicom_modality(val: Any) -> ModalityType | None:
    s = _str_or_none(val)
    if not s:
        return None
    try:
        return ModalityType(s)
    except ValueError:
        return None


def _image_type_tokens(ds: pydicom.dataset.FileDataset) -> set[str]:
    raw = getattr(ds, "ImageType", None)
    if raw is None:
        return set()
    # pydicom MultiValue is iterable but not a list/tuple
    if isinstance(raw, str):
        parts = raw.split("\\")
    else:
        try:
            parts = [str(x) for x in raw]
        except TypeError:
            parts = str(raw).split("\\")
    return {p.strip().upper() for p in parts if p and str(p).strip()}


def _infer_modality(
    dicom_modality: ModalityType | None, image_type: set[str]
) -> Modality | None:
    if dicom_modality is ModalityType.OPT:
        return Modality.OCT
    if dicom_modality is ModalityType.OP:
        if "RED" in image_type:
            return Modality.InfraredReflectance
        if "AF" in image_type:
            return Modality.Autofluorescence
    return None


def _parse_study_date(ds: pydicom.dataset.FileDataset) -> date | None:
    d = getattr(ds, "StudyDate", None)
    if not d:
        return None
    try:
        if isinstance(d, DA):
            return d
        s = str(d).strip()
        if len(s) >= 8:
            return datetime.strptime(s[:8], "%Y%m%d").date()
    except (TypeError, ValueError):
        return None
    return None


def _parse_acquisition_datetime(ds: pydicom.dataset.FileDataset) -> datetime | None:
    dt_val = getattr(ds, "AcquisitionDateTime", None)
    if dt_val:
        try:
            s = str(dt_val).strip()
            if len(s) >= 14:
                return datetime.strptime(s[:14], "%Y%m%d%H%M%S")
        except (TypeError, ValueError):
            pass
    d = getattr(ds, "AcquisitionDate", None)
    t = getattr(ds, "AcquisitionTime", None)
    if not d and not t:
        return None
    try:
        ds_part = str(d) if d else "19700101"
        if isinstance(d, DA):
            ds_part = d.strftime("%Y%m%d")
        tm_part = str(t) if t else "000000"
        if isinstance(t, TM):
            tm_part = t.strftime("%H%M%S.%f").replace(".000000", "").rstrip(".")
        combined = (ds_part + tm_part.replace(":", ""))[:14]
        return datetime.strptime(combined.ljust(14, "0"), "%Y%m%d%H%M%S")
    except (TypeError, ValueError):
        return None


def _collect_referenced_sop_uids(ds: pydicom.dataset.FileDataset) -> list[str]:
    """Collect ReferencedSOPInstanceUID values used to link OCT → enface."""
    found: list[str] = []
    seen: set[str] = set()

    def _add(uid: Any) -> None:
        s = _str_or_none(uid)
        if s and s not in seen:
            seen.add(s)
            found.append(s)

    def _from_seq(seq: Any) -> None:
        if not seq:
            return
        for item in seq:
            _add(getattr(item, "ReferencedSOPInstanceUID", None))
            ofl = getattr(item, "OphthalmicFrameLocationSequence", None)
            if ofl:
                for loc in ofl:
                    _add(getattr(loc, "ReferencedSOPInstanceUID", None))

    _from_seq(getattr(ds, "ReferencedImageSequence", None))

    shared = getattr(ds, "SharedFunctionalGroupsSequence", None)
    if shared:
        for fg in shared:
            _from_seq(getattr(fg, "ReferencedImageSequence", None))

    per_frame = getattr(ds, "PerFrameFunctionalGroupsSequence", None)
    if per_frame:
        # First frame is enough to identify the enface localizer.
        _from_seq(getattr(per_frame[0], "OphthalmicFrameLocationSequence", None))
        _from_seq(getattr(per_frame[0], "ReferencedImageSequence", None))

    return found


def strip_link_meta(state: dict[str, Any]) -> dict[str, Any]:
    """Remove linker-only keys before ``ImportRow`` validation."""
    return {k: v for k, v in state.items() if k not in LINK_META_KEYS}


def _float_pair(val: Any) -> tuple[float, float] | None:
    """Parse DICOM PixelSpacing-like values (MultiValue or backslash-separated)."""
    if val is None:
        return None
    try:
        if isinstance(val, str):
            parts = [float(x) for x in val.split("\\") if x.strip()]
        else:
            parts = [float(x) for x in val]
    except (TypeError, ValueError):
        try:
            parts = [float(x) for x in str(val).split("\\") if x.strip()]
        except (TypeError, ValueError):
            return None
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def _apply_pixel_spacing(out: dict[str, Any], spacing: Any) -> None:
    """DICOM PixelSpacing is row\\col → resolution_vertical / resolution_horizontal."""
    if out.get("resolution_horizontal") is not None and out.get("resolution_vertical") is not None:
        return
    pair = _float_pair(spacing)
    if not pair:
        return
    row_spacing, col_spacing = pair
    if out.get("resolution_vertical") is None:
        out["resolution_vertical"] = row_spacing
    if out.get("resolution_horizontal") is None:
        out["resolution_horizontal"] = col_spacing


def _apply_slice_thickness(out: dict[str, Any], thickness: Any) -> None:
    if out.get("resolution_axial") is not None or thickness is None:
        return
    try:
        out["resolution_axial"] = float(thickness)
    except (TypeError, ValueError):
        pass


def _pixel_measures_from_functional_groups(
    ds: pydicom.dataset.FileDataset,
) -> tuple[Any, Any]:
    """
    Read PixelSpacing / SliceThickness from SharedFunctionalGroupsSequence
    (common for Ophthalmic Tomography / multi-frame OPT).
    """
    spacing = None
    thickness = None
    shared = getattr(ds, "SharedFunctionalGroupsSequence", None)
    if not shared:
        return None, None
    for fg in shared:
        pm_seq = getattr(fg, "PixelMeasuresSequence", None)
        if not pm_seq:
            continue
        pm = pm_seq[0]
        if spacing is None:
            spacing = getattr(pm, "PixelSpacing", None)
        if thickness is None:
            thickness = getattr(pm, "SliceThickness", None)
        if spacing is not None and thickness is not None:
            break
    return spacing, thickness


def dicom_header_patches_from_bytes(raw: bytes) -> dict[str, Any]:
    """
    Parse DICOM metadata without loading pixel data.

    Keys match ``ImportRow`` / ``InstancePOST`` field names where possible.
    Also may include linker-only keys in ``LINK_META_KEYS``
    (``frame_of_reference_uid``, ``referenced_sop_instance_uids``).
    """
    ds = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True, force=True)
    out: dict[str, Any] = {}

    pid = _str_or_none(getattr(ds, "PatientID", None))
    if pid:
        out["patient_identifier"] = pid

    study_date = _parse_study_date(ds)
    if study_date is not None:
        out["study_date"] = study_date

    uid = _str_or_none(getattr(ds, "SOPInstanceUID", None))
    if uid:
        out["sop_instance_uid"] = uid
    scuid = _str_or_none(getattr(ds, "SOPClassUID", None))
    if scuid:
        out["sop_class_uid"] = scuid

    dm = _dicom_modality(getattr(ds, "Modality", None))
    if dm is not None:
        out["dicom_modality"] = dm

    modality = _infer_modality(dm, _image_type_tokens(ds))
    if modality is not None:
        out["modality"] = modality

    rows = getattr(ds, "Rows", None)
    cols = getattr(ds, "Columns", None)
    if rows is not None:
        try:
            out["height"] = int(rows)
        except (TypeError, ValueError):
            pass
    if cols is not None:
        try:
            out["width"] = int(cols)
        except (TypeError, ValueError):
            pass

    nf = getattr(ds, "NumberOfFrames", None)
    if nf is not None:
        try:
            n = int(str(nf).split("\\")[0])
            if n > 0:
                out["depth"] = n
        except (TypeError, ValueError):
            pass

    siuid = _str_or_none(getattr(ds, "SeriesInstanceUID", None))
    if siuid:
        out["series_instance_uid"] = siuid
    stuid = _str_or_none(getattr(ds, "StudyInstanceUID", None))
    if stuid:
        out["study_instance_uid"] = stuid

    sn = getattr(ds, "SeriesNumber", None)
    if sn is not None:
        try:
            out["series_number"] = int(sn)
        except (TypeError, ValueError):
            pass

    pi = _str_or_none(getattr(ds, "PhotometricInterpretation", None))
    if pi:
        out["photometric_interpretation"] = pi

    spp = getattr(ds, "SamplesPerPixel", None)
    if spp is not None:
        try:
            out["samples_per_pixel"] = int(spp)
        except (TypeError, ValueError):
            pass

    lat = _laterality(getattr(ds, "ImageLaterality", None))
    if lat is None:
        lat = _laterality(getattr(ds, "Laterality", None))
    if lat is not None:
        out["laterality"] = lat

    adt = _parse_acquisition_datetime(ds)
    if adt is not None:
        out["acquisition_date_time"] = adt

    _apply_pixel_spacing(out, getattr(ds, "PixelSpacing", None))
    _apply_slice_thickness(out, getattr(ds, "SliceThickness", None))

    # OPT volumes typically store measures in shared functional groups only
    fg_spacing, fg_thickness = _pixel_measures_from_functional_groups(ds)
    _apply_pixel_spacing(out, fg_spacing)
    _apply_slice_thickness(out, fg_thickness)

    for_uid = _str_or_none(getattr(ds, "FrameOfReferenceUID", None))
    if for_uid:
        out["frame_of_reference_uid"] = for_uid

    refs = _collect_referenced_sop_uids(ds)
    if refs:
        out["referenced_sop_instance_uids"] = refs

    return out
