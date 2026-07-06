from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import zarr

from .zarr_array import ZarrArray


class ZarrStorageManager:
    def __init__(self, store_path: str | Path):
        self.store_path = store_path
        self.root = zarr.open_group(store=store_path, mode="a")
        self._open_arrays: Dict[Tuple, ZarrArray] = {}

    def _get_array_name(self, dtype: np.dtype, shape: Tuple) -> str:
        shape_str = "_".join(str(dim) for dim in shape)
        return f"{str(dtype)}_{shape_str}.zarr"

    def get_array(self, group_name: str, dtype: np.dtype, shape: Tuple) -> ZarrArray:
        array_name = self._get_array_name(dtype, shape)
        array_shape = (0,) + shape
        group = self.root.require_group(group_name)
        array = group.get(array_name, None)
        if array is None:
            array = group.create_array(
                name=array_name,
                shape=array_shape,
                chunks=(1, *shape),
                dtype=dtype,
                overwrite=False,
            )
        return ZarrArray(array)

    def read(
        self,
        group_name: str,
        data_dtype: np.dtype,
        data_shape: Tuple[int],
        zarr_index: int,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ):
        zarr_array = self.get_array(group_name, data_dtype, data_shape)
        if (axis is not None) != (slice_index is not None):
            raise ValueError(
                "Both axis and slice_index must be provided together for slice operations"
            )
        if axis is not None and slice_index is not None:
            return zarr_array.read_slice(zarr_index, axis, slice_index)
        return zarr_array.read(zarr_index)

    def write(
        self,
        group_name: str,
        data_dtype: np.dtype,
        data_shape: Tuple[int],
        data: np.ndarray,
        zarr_index: Optional[int] = None,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> int:
        zarr_array = self.get_array(group_name, data_dtype, data_shape)

        if len(data.shape) == 2 and slice_index is None:
            if axis is None:
                raise ValueError("axis must be provided for 2D writes")
            slice_index = 0

        if (axis is not None) != (slice_index is not None):
            raise ValueError(
                "Both axis and slice_index must be provided together for slice operations"
            )

        if axis is not None and slice_index is not None:
            return zarr_array.write_slice(zarr_index, axis, slice_index, data)
        return zarr_array.write(zarr_index, data)
