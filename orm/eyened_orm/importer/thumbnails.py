import hashlib
import hmac
from pathlib import Path

import cv2
import numpy as np
import pydicom
from PIL import Image
from sqlalchemy import func, select
from tqdm import tqdm

from eyened_orm import ImageInstance, Modality


def get_thumbnail_dicom(im: ImageInstance):
    ds = pydicom.read_file(im.path)
    ds.decompress()

    if ds.pixel_array is None:
        return None
    array_dimension = ds.pixel_array.ndim
    if ds.Modality in ["OP", "SC"]:
        assert ds.pixel_array.ndim == 2 or (
            ds.pixel_array.ndim == 3 and ds.pixel_array.shape[-1] in [1, 3]
        )
        im = ds.pixel_array
    elif ds.Modality == "OPT":
        if array_dimension == 2:
            im = ds.pixel_array
        elif array_dimension == 3:
            # enface image
            im = ds.pixel_array.mean(axis=1)  # first base scan
            size = np.max(im.shape)
            im = cv2.resize(im, (size, size), interpolation=cv2.INTER_LINEAR)
        else:
            raise ValueError("Invalid array dimension")
    else:
        raise ValueError(f"Invalid modality {ds.Modality}")

    return im


def open_dot_binary(im: ImageInstance):
    with open(im.path, "rb") as f:
        raw = np.frombuffer(f.read(), dtype=np.uint8)
        data = raw.reshape((-1, im.Rows_y, im.Columns_x), order="C")
    return data


def get_thumbnail_binary(im: ImageInstance):
    data = open_dot_binary(im)
    im = data.mean(axis=1)
    size = np.max(im.shape)
    return cv2.resize(im, (size, size), interpolation=cv2.INTER_LINEAR)


def get_thumbnail_other(im: ImageInstance):
    return np.array(Image.open(im.path))


def get_thumbnail(im: ImageInstance):
    if im.DatasetIdentifier.endswith(".dcm"):
        np_im = get_thumbnail_dicom(im)
    elif im.DatasetIdentifier.endswith(".binary"):
        np_im = get_thumbnail_binary(im)
    else:
        np_im = get_thumbnail_other(im)

    if im.Modality == Modality.ColorFundus and im.CFROI:
        if "success" not in im.CFROI or im.CFROI["success"]:
            np_im = preprocess(np_im, im.CFROI)

    return np_im


def generate_hash(db_id, secret_key):
    # Use HMAC-SHA256 for cryptographic security
    hash_bytes = hmac.new(
        secret_key.encode(), str(db_id).encode(), hashlib.sha256
    ).hexdigest()
    return hash_bytes


def preprocess(image: np.ndarray, bounds: dict):
    from rtnls_fundusprep.cfi_bounds import CFIBounds

    bounds = CFIBounds(**bounds, image=image)
    _, bounds_cropped = bounds.crop(512)

    return bounds_cropped.image


def save_thumbnails(
    im: ImageInstance, thumbnails_basepath: Path, secret: str, sizes=[144, 540]
):
    project_path = thumbnails_basepath / str(im.Patient.Project.ProjectID)
    if not project_path.exists():
        project_path.mkdir(parents=True)

    np_im = get_thumbnail(im).squeeze()

    if np_im.ndim == 2:
        pil_im = Image.fromarray(np_im, "L")
    elif np_im.ndim == 3:
        pil_im = Image.fromarray(np_im, "RGB")
    else:
        raise ValueError("Thumbnail must be 2D or 3D")

    thumbnail_identifier = f"{str(im.Patient.Project.ProjectID)}/{generate_hash(im.ImageInstanceID, secret)[:24]}"

    for size in sizes:
        thumb = pil_im.copy()
        thumb.thumbnail((size, size))

        thumb.save(
            thumbnails_basepath / f"{thumbnail_identifier}_{size}.jpg",
            format="JPEG",
            optimize=True,
            quality=75,
            progressive=True,
        )

    return thumbnail_identifier


def update_thumbnails_for_images(session, images, config, N=1000):
    for i, image in enumerate(tqdm(images)):
        if image.path.endswith(".json"):
            image.ThumbnailPath = None
        else:
            try:
                thumbnail_identifier = save_thumbnails(
                    image, Path(config["thumbnails_path"]), secret=config["secret_key"]
                )
            except Exception:
                thumbnail_identifier = ""
            image.ThumbnailPath = thumbnail_identifier

        if (i + 1) % N == 0:
            session.commit()
    session.commit()


def update_thumbnails(session, config, update_failed=False):
    where = (ImageInstance.ThumbnailPath == None)
    if update_failed:
        where = (where | (ImageInstance.ThumbnailPath == ""))
    images = (
        session.execute(
            select(ImageInstance)
            .where(where)
            .order_by(func.random())
        )
        .scalars()
        .all()
    )
    print(f"Found {len(images)} images without thumbnails")

    update_thumbnails_for_images(session, images, config)
