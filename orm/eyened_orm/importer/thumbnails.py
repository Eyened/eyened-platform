import cv2
import numpy as np
from PIL import Image
from pathlib import Path
import os
from tqdm import tqdm

from eyened_orm import ImageInstance, Modality


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
    project_id = str(im.Patient.Project.ProjectID)
    thumbnail_name = im.PublicID
    return f"{project_id}/{thumbnail_name}"


def save_thumbnails(im: ImageInstance, sizes=[144, 540]):
    thumnails_folder = os.environ.get("EYENED_THUMBNAILS_FOLDER")
    if im.Modality == Modality.ColorFundus:
        _, bounds_cropped = im.bounds.crop(max(sizes))
        np_im = bounds_cropped.image
    else:
        np_im = get_thumbnail(im)
    pil_im = Image.fromarray(np_im)

    # Save thumbnails for each size

    for size in sizes:
        thumb = pil_im.copy()
        thumb.thumbnail((size, size))
        thumb_filename = im.get_thumbnail_filename(size)
        thumb_path = Path(thumnails_folder) / thumb_filename
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        thumb.save(
            thumb_path,
            format="JPEG",
            optimize=True,
            quality=75,
            progressive=True,
        )


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
