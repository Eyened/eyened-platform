import hashlib
import hmac

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import func, select
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
                return pixel_array.squeeze()
            elif n_scans < 10:
                return pixel_array[n_scans // 2]
            else:
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


def generate_thumbnail_name(db_id, secret_key):
    # default to the db_id if no secret key is provided
    if secret_key is None:
        return str(db_id)
    # otherwise generate a hash of the db_id and the secret key for obfuscation
    hash_bytes = hmac.new(
        secret_key.encode(), str(db_id).encode(), hashlib.sha256
    ).hexdigest()
    return hash_bytes


def get_thumbnail_identifier(im: ImageInstance) -> str:
    """Generate a unique identifier for the thumbnail."""
    secret_key = ImageInstance.config.secret_key
    project_id = str(im.Patient.Project.ProjectID)
    thumbnail_name = generate_thumbnail_name(im.ImageInstanceID, secret_key)[:24]
    return f"{project_id}/{thumbnail_name}"


def save_thumbnails(im: ImageInstance, sizes=[144, 540]):

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
        thumb_path = im.get_thumbnail_path(size)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        thumb.save(
            thumb_path,
            format="JPEG",
            optimize=True,
            quality=75,
            progressive=True,
        )


def get_missing_thumbnail_images(session, where, include_failed=False):
    where = ImageInstance.ThumbnailPath == None
    if include_failed:
        where = where | (ImageInstance.ThumbnailPath == "")

    images = (
        session.execute(select(ImageInstance).where(where).order_by(func.random()))
        .scalars()
        .all()
    )
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
            if image.path.suffix == ".json":
                image.ThumbnailPath = None
                print(f"Skipping {image.ImageInstanceID} because it is a JSON file")
            else:
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
