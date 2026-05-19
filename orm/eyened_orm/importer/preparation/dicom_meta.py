from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pydicom
from pydicom.valuerep import DA, TM

from eyened_orm.image_instance import Laterality, ModalityType


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


def dicom_header_patches_from_bytes(raw: bytes) -> dict[str, Any]:
    """
    Parse DICOM metadata without loading pixel data.

    Keys match ``ImportRow`` / ``InstancePOST`` field names where possible.
    """
    ds = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True, force=True)
    out: dict[str, Any] = {}

    uid = _str_or_none(getattr(ds, "SOPInstanceUID", None))
    if uid:
        out["sop_instance_uid"] = uid
    scuid = _str_or_none(getattr(ds, "SOPClassUID", None))
    if scuid:
        out["sop_class_uid"] = scuid

    dm = _dicom_modality(getattr(ds, "Modality", None))
    if dm is not None:
        out["dicom_modality"] = dm

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

    ps = getattr(ds, "PixelSpacing", None)
    if ps is not None:
        try:
            parts = [float(x) for x in str(ps).split("\\") if x.strip()]
            if len(parts) >= 2:
                out["resolution_horizontal"] = parts[1]
                out["resolution_vertical"] = parts[0]
        except (TypeError, ValueError):
            pass

    st = getattr(ds, "SliceThickness", None)
    if st is not None:
        try:
            out["resolution_axial"] = float(st)
        except (TypeError, ValueError):
            pass

    return out
