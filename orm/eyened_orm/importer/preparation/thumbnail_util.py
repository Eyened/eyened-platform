from __future__ import annotations

import io
import uuid
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image

from eyened_orm.data_access import load_storage_root


def allocate_thumbnail_path(project_id: int) -> str:
    """
    Random thumbnail identifier (relative path prefix under the thumbnails root).

    Layout: ``{project_id}/{2-char bucket}/{uuid}`` (no file extension).
    """
    u = uuid.uuid4().hex
    return f"{project_id}/{u[:2]}/{u}"


def thumbnail_filename(thumbnail_path: str, size: int) -> str:
    """Filename fragment stored under the thumbnails root (matches ``ImageInstance``)."""
    return f"{thumbnail_path}_{size}.jpg"


def pil_image_from_raster_bytes(raw: bytes) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as im:
        im.seek(0)
        return im.convert("RGB")


def _thumbnail_slice_from_pixel_array(
    pixel_array: np.ndarray,
    *,
    resolution_horizontal: float | None = None,
    resolution_vertical: float | None = None,
) -> np.ndarray:
    """
    Apply the same 2D slice / projection policy as ``get_thumbnail`` in
    ``importer/thumbnails.py``, but purely on a numpy array (no ORM).
    """
    shape = pixel_array.shape
    if len(shape) == 3:
        # grayscale / RGB(A)-like
        if shape[2] <= 4:
            return pixel_array.squeeze()

        # OCT-like volume: shape ~ (n_scans, H, W)
        n_scans, _, _ = pixel_array.shape
        if n_scans == 1:
            return pixel_array.squeeze()
        if n_scans < 10:
            # few B-scans (take the middle one)
            return pixel_array[n_scans // 2]

        # many B-scans (create enface projection)
        np_im = pixel_array.mean(axis=1)
        try:
            np_im = np_im - np.min(np_im)
            np_im = np_im / np.max(np_im)
            np_im = (np_im * 255).astype(np.uint8)
        except ValueError:
            pass

        try:
            aspect_ratio = (
                float(resolution_horizontal) / float(resolution_vertical)
                if resolution_horizontal is not None and resolution_vertical not in (None, 0)
                else 1.0
            )
        except (TypeError, ZeroDivisionError):
            aspect_ratio = 1.0

        h, w = np_im.shape
        if aspect_ratio > 1:
            target_shape = (int(w * aspect_ratio), h)
        else:
            target_shape = (w, int(h / aspect_ratio))
        return cv2.resize(np_im, target_shape, interpolation=cv2.INTER_LINEAR)

    # already 2D or other shapes – keep as-is
    return pixel_array


def pil_image_from_dicom_bytes(raw: bytes) -> Image.Image:
    """Build a single 2D thumbnail source from DICOM bytes (loads pixels)."""
    ds = pydicom.dcmread(io.BytesIO(raw), force=True)
    arr = np.asarray(ds.pixel_array)
    # Try to preserve original behaviour, using pixel spacing if present
    res_h = None
    res_v = None
    ps = getattr(ds, "PixelSpacing", None)
    if ps is not None:
        try:
            parts = [float(x) for x in str(ps).split("\\") if x.strip()]
            if len(parts) >= 2:
                # Same convention as dicom_meta: [vertical, horizontal]
                res_v = parts[0]
                res_h = parts[1]
        except (TypeError, ValueError):
            pass

    sl = _thumbnail_slice_from_pixel_array(
        arr,
        resolution_horizontal=res_h,
        resolution_vertical=res_v,
    )
    # Ensure we end up with an RGB image for saving
    if sl.ndim == 2:
        rgb = np.stack([sl, sl, sl], axis=-1)
    else:
        rgb = sl
    rgb = np.clip(rgb, 0, None)
    if rgb.dtype != np.uint8:
        mx = float(rgb.max()) if rgb.size else 1.0
        if mx > 0:
            rgb = (rgb / mx * 255.0).astype(np.uint8)
        else:
            rgb = rgb.astype(np.uint8)
    return Image.fromarray(rgb)


def pil_image_for_thumbnail(raw: bytes, *, image_storage_format: str) -> Image.Image:
    if image_storage_format == "dicom":
        return pil_image_from_dicom_bytes(raw)
    return pil_image_from_raster_bytes(raw)


def generate_thumbnails_pil(
    pil_im: Image.Image, sizes: list[int]
) -> dict[int, Image.Image]:
    return {size: pil_im.copy().resize((size, size)) for size in sizes}


def persist_thumbnail_images(
    thumbnail_path: str,
    thumbnails: dict[int, Image.Image],
    *,
    thumbnails_folder: Path | None = None,
) -> dict[int, Path]:
    """Write JPEG thumbnails; paths match ``ImageInstance.get_thumbnail_filename`` layout."""
    root = thumbnails_folder if thumbnails_folder is not None else load_storage_root() / "thumbnails"
    written: dict[int, Path] = {}
    for size, thumb in thumbnails.items():
        name = thumbnail_filename(thumbnail_path, size)
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        thumb.save(
            path,
            format="JPEG",
            optimize=True,
            quality=75,
            progressive=True,
        )
        written[size] = path
    return written


def save_thumbnails_from_bytes(
    raw: bytes,
    *,
    image_storage_format: str,
    thumbnail_path: str,
    sizes: list[int] | None = None,
    thumbnails_folder: Path | None = None,
) -> dict[int, Path]:
    if sizes is None:
        sizes = [144, 540]
    sizes = sorted(set(sizes))
    pil_im = pil_image_for_thumbnail(raw, image_storage_format=image_storage_format)
    max_sz = max(sizes)
    if pil_im.width > max_sz or pil_im.height > max_sz:
        pil_im.thumbnail((max_sz, max_sz), Image.Resampling.LANCZOS)
    thumbs = generate_thumbnails_pil(pil_im, sizes)
    return persist_thumbnail_images(
        thumbnail_path, thumbs, thumbnails_folder=thumbnails_folder
    )
