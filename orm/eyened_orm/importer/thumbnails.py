from os import PathLike
import cv2
import numpy as np
from PIL import Image, ImageOps
from pathlib import Path

from sqlalchemy.orm import Session
from eyened_orm.commands.model_processing import run_cfi_attribute_pipeline
from eyened_orm.data_access import load_storage_root
from tqdm import tqdm

from eyened_orm import ImageInstance, Modality
from eyened_orm.importer.preparation.thumbnail_util import (
    allocate_thumbnail_path,
    persist_thumbnail_images,
)


def get_thumbnail(im: ImageInstance):

    pixel_array = im.pixel_array
    shape = pixel_array.shape
    if len(shape) == 3:
        if shape[2] <= 4:  # grayscale, RGB or RGBA
            return pixel_array.squeeze()
        else:  # OCT
            n_scans, _, _ = pixel_array.shape
            if n_scans == 1:
                # single B-scan
                return pixel_array.squeeze()
            elif n_scans < 10:
                # few B-scans (take the middle one)
                return pixel_array[n_scans // 2]
            else:
                # many B-scans (create enface projection)
                np_im = pixel_array.mean(axis=1)
                try:
                    np_im = np_im - np.min(np_im)
                    np_im = np_im / np.max(np_im)
                    np_im = (np_im * 255).astype(np.uint8)
                except ValueError:
                    pass

                try:
                    aspect_ratio = im.ResolutionHorizontal / im.ResolutionVertical
                except (TypeError, ZeroDivisionError):
                    aspect_ratio = 1

                h, w = np_im.shape
                if aspect_ratio > 1:
                    target_shape = (int(w * aspect_ratio), h)
                else:
                    target_shape = (w, int(h / aspect_ratio))

                return cv2.resize(np_im, target_shape, interpolation=cv2.INTER_LINEAR)
    else:
        return pixel_array


def get_thumbnail_identifier(im: ImageInstance) -> str:
    """Generate a unique identifier for the thumbnail."""
    return allocate_thumbnail_path(im.Patient.Project.ProjectID)


def generate_thumbnail_base_image(im: ImageInstance, *, max_size: int) -> Image.Image:
    """
    Generate a base PIL image from which thumbnails are derived.
    """
    if im.Modality == Modality.ColorFundus:
        bounds = im.bounds_with_image
        if bounds is None:
            raise ValueError("Bounds are not available for color fundus images")
        _, bounds_cropped = bounds.crop(max_size)
        np_im = bounds_cropped.image
    else:
        np_im = get_thumbnail(im)
    return Image.fromarray(np_im)


def generate_thumbnails(
    pil_im: Image.Image, sizes: list[int]
) -> dict[int, Image.Image]:
    """Generate square thumbnail images keyed by their size.

    Letterboxed: full image centered, aspect ratio preserved, border filled
    with zeros (per channel).
    """
    bands = pil_im.getbands()
    pad_color = 0 if len(bands) == 1 else (0,) * len(bands)
    resample = Image.Resampling.LANCZOS
    return {
        size: ImageOps.pad(pil_im, (size, size), method=resample, color=pad_color)
        for size in sizes
    }


def save_thumbnail_images(
    im: ImageInstance,
    thumbnails: dict[int, Image.Image],
    *,
    thumbnails_folder: Path,
) -> dict[int, Path]:
    """Persist thumbnail images to disk and return the written paths."""
    if not im.ThumbnailPath:
        raise ValueError("ThumbnailPath must be set before saving thumbnails")
    return persist_thumbnail_images(
        im.ThumbnailPath, thumbnails, thumbnails_folder=thumbnails_folder
    )


def save_thumbnails(
    im: ImageInstance, sizes: list[int] | None = None
) -> dict[int, Path]:
    if sizes is None:
        sizes = [144, 540]
    sizes = sorted(set(sizes))

    thumbnails_folder = load_storage_root() / "thumbnails"
    pil_im = generate_thumbnail_base_image(im, max_size=max(sizes))
    thumbs = generate_thumbnails(pil_im, sizes)
    return save_thumbnail_images(im, thumbs, thumbnails_folder=thumbnails_folder)


def get_missing_thumbnail_images(session, include_failed=False):
    where = ImageInstance.ThumbnailPath == None
    if include_failed:
        where = where | (ImageInstance.ThumbnailPath == "")
    images = ImageInstance.where(session, where)
    print(f"Found {len(images)} images without thumbnails")
    return images


def ensure_cfi_roi(session: Session, images: list[ImageInstance]):
    cfi_image_ids = [
        image.ImageInstanceID
        for image in images
        if image.Modality == Modality.ColorFundus
    ]
    if not cfi_image_ids:
        return
    run_cfi_attribute_pipeline(
        session,
        cfi_image_ids,
        "cfi-roi",
    )


def update_thumbnails(
    session: Session,
    images: list[ImageInstance],
    print_errors=False,
    commit_interval=100,
):
    ensure_cfi_roi(session, images)

    for i, image in enumerate(tqdm(images)):
        try:
            image.ThumbnailPath = get_thumbnail_identifier(image)
            save_thumbnails(image)
        except Exception as e:
            image.ThumbnailPath = ""
            if print_errors:
                print(
                    f"Error generating thumbnail for image {image.ImageInstanceID}: {e}"
                )

        session.add(image)
        if (i + 1) % commit_interval == 0:
            session.commit()
    session.commit()


def run_update_thumbnails_job(
    database=None,
    *,
    failed: bool = False,
    print_errors: bool = False,
) -> None:
    """Find images missing thumbnails, generate and persist them.

    Used by the ``eorm update-thumbnails`` CLI and the API RQ worker. Pass a
    :class:`~eyened_orm.Database` from :func:`~eyened_orm.commands.shared.get_database`
    in the CLI so connection info is printed; workers pass ``None`` and a new
    ``Database()`` is created from the environment.
    """
    from eyened_orm import Database

    db = database if database is not None else Database()
    with db.get_session() as session:
        images = get_missing_thumbnail_images(session, failed)
        update_thumbnails(session, images, print_errors=print_errors)


def run_update_thumbnails_for_image_ids_job(
    image_ids: list[int],
    *,
    database=None,
    print_errors: bool = False,
) -> None:
    """Generate thumbnails for the given instance IDs (regardless of prior ``ThumbnailPath``)."""
    from eyened_orm import Database

    db = database if database is not None else Database()
    with db.get_session() as session:
        run_update_thumbnails_for_image_ids(
            session, image_ids, print_errors=print_errors
        )


def run_update_thumbnails_for_image_ids(
    session: Session, image_ids: list[int], print_errors: bool = False
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
    update_thumbnails(session, images, print_errors=print_errors)
