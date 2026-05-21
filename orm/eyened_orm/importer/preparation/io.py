from __future__ import annotations

from pathlib import Path


def infer_storage_format(object_key: str) -> str:
    suffix = Path(object_key).suffix.lower()
    if suffix in {".dcm", ".dicom"}:
        return "dicom"
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".mhd":
        return "mhd"
    if suffix == "":
        return "png_series"
    return "binary"
