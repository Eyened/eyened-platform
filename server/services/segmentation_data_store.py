from __future__ import annotations

from typing import Optional, Protocol

import numpy as np
from eyened_orm.segmentation_storage import (
    read_segmentation_data,
    write_segmentation_data,
)


class SegmentationDataStore(Protocol):
    """Storage seam for segmentation binary data.

    The Service depends only on this contract; the concrete store decides the
    library. A future concurrency fix (a locking decorator, or a different
    backend) is a new implementation swapped in ``get_segmentation_data_store``
    without touching the Service, routes, or tests.
    """

    def read(
        self,
        segmentation,
        *,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> Optional[np.ndarray]: ...

    def write(
        self,
        segmentation,
        data: np.ndarray,
        *,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> int: ...


class ZarrSegmentationDataStore:
    """Production store: delegates to the zarr-backed ``segmentation_storage``
    module functions — the exact calls the route made before this refactor, so
    behavior is unchanged."""

    def read(
        self,
        segmentation,
        *,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        return read_segmentation_data(
            segmentation, axis=axis, slice_index=slice_index
        )

    def write(
        self,
        segmentation,
        data: np.ndarray,
        *,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> int:
        return write_segmentation_data(
            segmentation, data, axis=axis, slice_index=slice_index
        )


def get_segmentation_data_store() -> SegmentationDataStore:
    """Default data store for FastAPI ``Depends()`` wiring."""
    return ZarrSegmentationDataStore()
