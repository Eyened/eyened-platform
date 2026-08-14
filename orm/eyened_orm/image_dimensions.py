"""ImageInstance dimension parsing, validation, and repair helpers.

Pixels on disk are the source of truth. Reads must not mutate the ORM session;
mismatches raise so callers repair via ``eorm repair-image-dimensions``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from eyened_orm.image_instance import ImageInstance

__all__ = [
    "ImageDimensionMismatchError",
    "ImageDimensions",
    "apply_dimensions",
    "assert_dimensions_match",
    "blocking_dependents",
    "dimensions_compatible",
    "dimensions_from_array",
    "effective_n_frames",
]


@dataclass(frozen=True)
class ImageDimensions:
    """Canonical (depth, height, width) derived from a pixel array or DB columns."""

    n_frames: Optional[int]  # None means single-frame / unspecified in array layout
    rows_y: Optional[int]
    columns_x: Optional[int]

    @property
    def shape_dhw(self) -> tuple[int, int, int]:
        if self.rows_y is None or self.columns_x is None:
            raise ValueError("Cannot build shape_dhw with unset Rows_y/Columns_x")
        return (effective_n_frames(self.n_frames), self.rows_y, self.columns_x)


class ImageDimensionMismatchError(ValueError):
    """DB dimensions disagree with the loaded pixel array."""

    def __init__(
        self,
        *,
        image_instance_id: int | None,
        db: ImageDimensions | None,
        array: ImageDimensions,
        detail: str,
    ):
        self.image_instance_id = image_instance_id
        self.db = db
        self.array = array
        id_part = (
            f"ImageInstance {image_instance_id}"
            if image_instance_id is not None
            else "ImageInstance"
        )
        super().__init__(
            f"{id_part} dimension mismatch: {detail} "
            f"(db={_fmt_dims(db)}, array={_fmt_dims(array)}). "
            f"Run `eorm repair-image-dimensions` after clearing blocking dependents."
        )


def _fmt_dims(dims: ImageDimensions | None) -> str:
    if dims is None:
        return "(unset)"
    return f"(NrOfFrames={dims.n_frames!r}, Rows_y={dims.rows_y}, Columns_x={dims.columns_x})"


def effective_n_frames(n_frames: Optional[int]) -> int:
    """Treat None as 1 for single-frame images."""
    return 1 if n_frames is None else n_frames


def dimensions_from_array(array: np.ndarray) -> ImageDimensions:
    """Infer (frames, height, width) from a numpy pixel array.

    Layout conventions match historical ``_update_image_dimensions``:
    - 2D: (H, W) → single-frame
    - 3D with last dim ≤ 4: (H, W, C) RGB/RGBA → single-frame
    - 3D with last dim > 4: (D, H, W) volume
    """
    shape = array.shape
    if len(shape) == 2:
        h, w = shape
        return ImageDimensions(n_frames=None, rows_y=int(h), columns_x=int(w))
    if len(shape) == 3:
        if shape[2] > 4:
            n_frames, h, w = shape
            return ImageDimensions(
                n_frames=int(n_frames), rows_y=int(h), columns_x=int(w)
            )
        h, w, _ = shape
        return ImageDimensions(n_frames=None, rows_y=int(h), columns_x=int(w))
    raise ValueError(f"Unsupported pixel array shape: {shape}")


def dimensions_from_instance(image: ImageInstance) -> ImageDimensions:
    return ImageDimensions(
        n_frames=image.NrOfFrames,
        rows_y=image.Rows_y,  # type: ignore[arg-type]
        columns_x=image.Columns_x,  # type: ignore[arg-type]
    )


def dimensions_compatible(db: ImageDimensions, array: ImageDimensions) -> list[str]:
    """Return human-readable mismatch reasons (empty if compatible).

    Unset DB height/width are not compared (incomplete metadata). Frame count
    uses None↔1 equivalence.
    """
    errors: list[str] = []
    if db.rows_y is not None and db.rows_y != array.rows_y:
        errors.append(f"Rows_y {db.rows_y} != {array.rows_y}")
    if db.columns_x is not None and db.columns_x != array.columns_x:
        errors.append(f"Columns_x {db.columns_x} != {array.columns_x}")
    if effective_n_frames(db.n_frames) != effective_n_frames(array.n_frames):
        # Only complain when DB explicitly set frames, or array is multi-frame
        if db.n_frames is not None or effective_n_frames(array.n_frames) > 1:
            errors.append(
                f"NrOfFrames {db.n_frames!r} != {array.n_frames!r}"
            )
    return errors


def assert_dimensions_match(image: ImageInstance, array: np.ndarray) -> None:
    """Raise if set DB dimensions disagree with ``array``. Does not mutate ``image``."""
    array_dims = dimensions_from_array(array)
    db_dims = ImageDimensions(
        n_frames=image.NrOfFrames,
        rows_y=image.Rows_y,  # may be None
        columns_x=image.Columns_x,
    )
    errors = dimensions_compatible(db_dims, array_dims)
    if errors:
        raise ImageDimensionMismatchError(
            image_instance_id=getattr(image, "ImageInstanceID", None),
            db=db_dims,
            array=array_dims,
            detail="; ".join(errors),
        )


def apply_dimensions(image: ImageInstance, array_dims: ImageDimensions) -> dict:
    """Set instance dimensions from array dims. Returns before/after for audit.

    Single-frame arrays store ``NrOfFrames=1`` (explicit convention).
    """
    before = {
        "Rows_y": image.Rows_y,
        "Columns_x": image.Columns_x,
        "NrOfFrames": image.NrOfFrames,
    }
    image.Rows_y = array_dims.rows_y
    image.Columns_x = array_dims.columns_x
    image.NrOfFrames = effective_n_frames(array_dims.n_frames)
    after = {
        "Rows_y": image.Rows_y,
        "Columns_x": image.Columns_x,
        "NrOfFrames": image.NrOfFrames,
    }
    return {"old": before, "new": after}


def blocking_dependents(image: ImageInstance) -> list[str]:
    """Reasons repair must not overwrite dimensions (operator must clear first)."""
    reasons: list[str] = []
    segs = getattr(image, "Segmentations", None) or []
    active = [s for s in segs if not getattr(s, "Inactive", False)]
    if active:
        reasons.append(f"{len(active)} segmentation(s)")
    if getattr(image, "CFROI", None) is not None:
        reasons.append("CFROI")
    if getattr(image, "CFKeypoints", None) is not None:
        reasons.append("CFKeypoints")
    return reasons
