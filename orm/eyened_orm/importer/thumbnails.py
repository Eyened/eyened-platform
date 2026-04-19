import cv2
import numpy as np
from PIL import Image
from pathlib import Path
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
        bounds = im.bounds
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
    """Generate resized thumbnail images keyed by their size."""
    return {size: pil_im.copy().resize((size, size)) for size in sizes}


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


def update_thumbnails(
    session,
    images,
    print_errors=False,
    N=100,
):
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
        if (i + 1) % N == 0:
            session.commit()
    session.commit()
