"""Thumbnail generation for :class:`~eyened_orm.ImageInstance` records.

Shared by:
- :class:`~eyened_orm.importer.postimport.PostImport` (after import)
- ``eorm update-thumbnails`` (CLI bulk repair)
- API RQ workers (``run_update_thumbnails_*_job``)
"""

from __future__ import annotations

import uuid
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
from sqlalchemy.orm import Session
from tqdm import tqdm

from eyened_orm import Database, ImageInstance, Modality
from eyened_orm.data_access import load_storage_root

THUMBNAIL_SIZES: tuple[int, ...] = (144, 540)
THUMBNAIL_COMMIT_INTERVAL = 100


def thumbnails_folder() -> Path:
    """Absolute path to the thumbnails storage root."""
    return load_storage_root() / "thumbnails"


def allocate_thumbnail_path(project_id: int) -> str:
    """Random path prefix under the thumbnails root: ``{project_id}/{bucket}/{uuid}``."""
    u = uuid.uuid4().hex
    return f"{project_id}/{u[:2]}/{u}"


def thumbnail_filename(thumbnail_path: str, size: int) -> str:
    return f"{thumbnail_path}_{size}.jpg"


def pixel_array_to_2d(
    pixel_array: np.ndarray,
    *,
    resolution_horizontal: float | None,
    resolution_vertical: float | None,
) -> np.ndarray:
    """Reduce a volume or multi-channel array to a displayable 2D slice.

    For OCT volumes this produces either a middle B-scan or an enface projection.
    """
    shape = pixel_array.shape
    if len(shape) == 3:
        if shape[2] <= 4:  # grayscale, RGB or RGBA
            return pixel_array.squeeze()
        # OCT volume: shape is (n_scans, H, W)
        n_scans, _, _ = shape
        if n_scans == 1:
            return pixel_array.squeeze()
        if n_scans < 10:
            # few B-scans (take the middle one)
            return pixel_array[n_scans // 2]
        # many B-scans: enface projection
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
                if resolution_horizontal is not None
                and resolution_vertical not in (None, 0)
                else 1.0
            )
        except (TypeError, ZeroDivisionError):
            aspect_ratio = 1.0
        h, w = np_im.shape
        target_shape = (
            (int(w * aspect_ratio), h) if aspect_ratio > 1 else (w, int(h / aspect_ratio))
        )
        return cv2.resize(np_im, target_shape, interpolation=cv2.INTER_LINEAR)
    return pixel_array


def build_base_pil_image(im: ImageInstance, *, max_size: int) -> Image.Image:
    """Build the source PIL image from which thumbnails are derived.

    For color fundus images the image is cropped to the CFI bounds.
    If bounds are unavailable a warning is printed and the full image is used.
    """
    res_h = im.ResolutionHorizontal
    res_v = im.ResolutionVertical
    if im.Modality == Modality.ColorFundus:
        bounds = im.bounds_with_image
        if bounds is not None:
            _, bounds_cropped = bounds.crop(max_size)
            np_im = bounds_cropped.image
        else:
            print(
                f"Warning: CFI bounds not available for image {im.ImageInstanceID}, "
                "using full image for thumbnail"
            )
            np_im = pixel_array_to_2d(
                im.pixel_array,
                resolution_horizontal=res_h,
                resolution_vertical=res_v,
            )
    else:
        np_im = pixel_array_to_2d(
            im.pixel_array,
            resolution_horizontal=res_h,
            resolution_vertical=res_v,
        )
    return Image.fromarray(np_im)


def render_square_thumbnails(
    pil_im: Image.Image, sizes: tuple[int, ...]
) -> dict[int, Image.Image]:
    """Letterbox to square thumbnails keyed by size."""
    bands = pil_im.getbands()
    # border filled with zeros (per channel)
    pad_color = 0 if len(bands) == 1 else (0,) * len(bands)
    resample = Image.Resampling.LANCZOS
    return {
        size: ImageOps.pad(pil_im, (size, size), method=resample, color=pad_color)
        for size in sizes
    }


def persist_thumbnail_images(
    thumbnail_path: str,
    thumbnails: dict[int, Image.Image],
    thumbnails_folder: Path,
) -> dict[int, Path]:
    # layout matches ``ImageInstance.get_thumbnail_filename``
    written: dict[int, Path] = {}
    for size, thumb in thumbnails.items():
        path = thumbnails_folder / thumbnail_filename(thumbnail_path, size)
        path.parent.mkdir(parents=True, exist_ok=True)
        thumb.save(path, format="JPEG", optimize=True, quality=75, progressive=True)
        written[size] = path
    return written


def save_thumbnails(
    im: ImageInstance,
    *,
    thumbnail_path: str,
    thumbnails_folder: Path,
    sizes: tuple[int, ...],
) -> dict[int, Path]:
    pil_im = build_base_pil_image(im, max_size=max(sizes))
    thumbs = render_square_thumbnails(pil_im, sizes)
    return persist_thumbnail_images(thumbnail_path, thumbs, thumbnails_folder)


def get_missing_thumbnail_images(
    session: Session, include_failed: bool
) -> list[ImageInstance]:
    # NULL: never generated; "" : previous generation failed
    where = ImageInstance.ThumbnailPath == None
    if include_failed:
        where = where | (ImageInstance.ThumbnailPath == "")
    images = ImageInstance.where(session, where)
    print(f"Found {len(images)} images without thumbnails")
    return images


def _needs_cfi_roi(im: ImageInstance) -> bool:
    if im.Modality != Modality.ColorFundus:
        return False
    roi = im.roi
    if roi is None:
        return True
    return roi.get("success") is False


def ensure_cfi_roi_for_thumbnails(session: Session, images: list[ImageInstance]) -> None:
    """Run CFI ROI on ColorFundus images missing a usable ``CFI_ROI`` attribute."""
    from eyened_orm.commands.model_processing import run_cfi_attribute_pipeline

    image_ids = [im.ImageInstanceID for im in images if _needs_cfi_roi(im)]
    if not image_ids:
        return
    # overwrite=True so previously failed ROI detections are retried
    run_cfi_attribute_pipeline(session, image_ids, "cfi-roi", overwrite=True)


def update_thumbnails(
    session: Session,
    images: list[ImageInstance],
    *,
    thumbnails_folder: Path,
    sizes: tuple[int, ...],
    print_errors: bool,
) -> None:
    ensure_cfi_roi_for_thumbnails(session, images)
    for i, image in enumerate(tqdm(images)):
        try:
            thumbnail_path = allocate_thumbnail_path(image.Patient.Project.ProjectID)
            image.ThumbnailPath = thumbnail_path
            save_thumbnails(
                image,
                thumbnail_path=thumbnail_path,
                thumbnails_folder=thumbnails_folder,
                sizes=sizes,
            )
        except Exception as e:
            image.ThumbnailPath = ""  # mark failed (see ImageInstance.ThumbnailPath)
            if print_errors:
                print(
                    f"Error generating thumbnail for image {image.ImageInstanceID}: {e}"
                )
        session.add(image)
        if (i + 1) % THUMBNAIL_COMMIT_INTERVAL == 0:
            session.commit()
    session.commit()


def run_update_thumbnails_for_image_ids(
    session: Session,
    image_ids: list[int],
    *,
    thumbnails_folder: Path,
    sizes: tuple[int, ...],
    print_errors: bool,
) -> None:
    ids = set(image_ids)
    images = ImageInstance.by_ids(session, ids)
    if len(images) != len(ids):
        found = {im.ImageInstanceID for im in images}
        missing = ids - found
        print(
            f"Thumbnail job: skipping {len(missing)} unknown ImageInstanceID(s): "
            f"{sorted(missing)[:20]}{'...' if len(missing) > 20 else ''}"
        )
    if not images:
        print("No images to process")
        return
    update_thumbnails(
        session,
        images,
        thumbnails_folder=thumbnails_folder,
        sizes=sizes,
        print_errors=print_errors,
    )


def run_update_thumbnails_job(
    database: Database,
    *,
    include_failed: bool,
    print_errors: bool,
) -> None:
    """Find images missing thumbnails, generate and persist them.

    Used by the ``eorm update-thumbnails`` CLI and the API RQ worker.
    """
    folder = thumbnails_folder()
    with database.get_session() as session:
        images = get_missing_thumbnail_images(session, include_failed)
        update_thumbnails(
            session,
            images,
            thumbnails_folder=folder,
            sizes=THUMBNAIL_SIZES,
            print_errors=print_errors,
        )


def run_update_thumbnails_for_image_ids_job(
    database: Database,
    image_ids: list[int],
    *,
    print_errors: bool,
) -> None:
    """Generate thumbnails for the given instance IDs (regardless of prior ``ThumbnailPath``)."""
    folder = thumbnails_folder()
    with database.get_session() as session:
        run_update_thumbnails_for_image_ids(
            session,
            image_ids,
            thumbnails_folder=folder,
            sizes=THUMBNAIL_SIZES,
            print_errors=print_errors,
        )
