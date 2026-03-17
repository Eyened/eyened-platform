from typing import Optional

import numpy as np
from eyened_orm import ModelSegmentation, Segmentation

from server.utils.zarr.manager import ZarrStorageManager
from functools import lru_cache


@lru_cache
def get_zarr_storage_manager() -> ZarrStorageManager:
    from server.config import settings

    return ZarrStorageManager(settings.zarr_store)


SegmentationLike = Segmentation | ModelSegmentation


def write_segmentation_data(
    segmentation: SegmentationLike,
    data: np.ndarray,
    axis: Optional[int] = None,
    slice_index: Optional[int] = None,
) -> int:
    """Write segmentation data through the configured storage backend."""
    if not segmentation.ImageInstance:
        raise ValueError("Segmentation has no associated ImageInstance")
    storage_manager = get_zarr_storage_manager()

    zarr_index = storage_manager.write(
        group_name=segmentation.groupname,
        data_dtype=segmentation.dtype,
        data_shape=segmentation.shape,
        data=data,
        zarr_index=segmentation.ZarrArrayIndex,
        axis=axis,
        slice_index=slice_index,
    )

    # For sparse annotations, append newly written slice index.
    if (
        segmentation.ScanIndices is not None
        and segmentation.is_sparse
        and axis == segmentation.SparseAxis
    ):
        if slice_index not in segmentation.ScanIndices:
            scan_indices = segmentation.ScanIndices.copy()
            scan_indices.append(slice_index)
            segmentation.ScanIndices = scan_indices

    segmentation.ZarrArrayIndex = zarr_index
    return zarr_index


def read_segmentation_data(
    segmentation: SegmentationLike,
    axis: Optional[int] = None,
    slice_index: Optional[int] = None,
) -> Optional[np.ndarray]:
    """Read segmentation data through the configured storage backend."""
    if segmentation.ZarrArrayIndex is None:
        return None

    if not segmentation.ImageInstance:
        raise ValueError("Segmentation has no associated ImageInstance")

    storage_manager = get_zarr_storage_manager()
    return storage_manager.read(
        group_name=segmentation.groupname,
        data_dtype=segmentation.dtype,
        data_shape=segmentation.shape,
        zarr_index=segmentation.ZarrArrayIndex,
        axis=axis,
        slice_index=slice_index,
    )
