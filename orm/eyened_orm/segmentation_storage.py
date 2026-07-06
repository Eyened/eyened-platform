from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

from eyened_orm.utils.zarr.manager import ZarrStorageManager


def _resolve_zarr_store_path() -> str:
    storage_root = os.getenv("EYENED_STORAGE_ROOT", "").strip()
    if not storage_root:
        return "/storage/segmentations.zarr"
    return str(Path(storage_root) / "segmentations.zarr")


@lru_cache
def get_zarr_storage_manager() -> ZarrStorageManager:
    return ZarrStorageManager(_resolve_zarr_store_path())


def write_segmentation_data(
    segmentation,
    data: np.ndarray,
    axis: Optional[int] = None,
    slice_index: Optional[int] = None,
) -> int:
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
    segmentation,
    axis: Optional[int] = None,
    slice_index: Optional[int] = None,
) -> Optional[np.ndarray]:
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
