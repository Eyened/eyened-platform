from __future__ import annotations

import io
from typing import Any

from PIL import Image


def raster_image_header_patches_from_bytes(raw: bytes) -> dict[str, Any]:
    """
    Infer width / height / frame count from a raster image using Pillow.

    Suitable for ``image/png``, ``image/jpeg``, and other PIL-supported formats.
    """
    out: dict[str, Any] = {}
    with Image.open(io.BytesIO(raw)) as im:
        out["width"] = int(im.width)
        out["height"] = int(im.height)
        n_frames = getattr(im, "n_frames", 1)
        try:
            n = int(n_frames)
        except (TypeError, ValueError):
            n = 1
        if n > 1:
            out["depth"] = n
    return out
