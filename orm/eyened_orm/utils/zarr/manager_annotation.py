from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import zarr

from .annotation_array import AnnotationZarrArray


class AnnotationZarrStorageManager:
    """
    A singleton manager class for creating and managing zarr arrays for annotation data.

    This class handles the creation, existence checking, and retrieval of zarr arrays
    based on annotation dtypes and image shapes. Arrays are stored with names that
    encode the annotation dtype and image dimensions.
    """

    def __init__(self, store_path: str | Path):
        self.root = zarr.open_group(store=store_path, mode="a")
        self._open_arrays: Dict[Tuple, AnnotationZarrArray] = {}

    def _get_array_name(
        self, annotation_dtype: np.dtype, annotation_shape: Tuple
    ) -> str:
        shape_str = "_".join(str(dim) for dim in annotation_shape)
        return f"{str(annotation_dtype)}_{shape_str}.zarr"

    def _get_array_key(
        self, group_name: str, annotation_dtype: np.dtype, annotation_shape: Tuple
    ) -> Tuple:
        return (group_name, annotation_dtype, *annotation_shape)

    def get_array(
        self, group_name: str, annotation_dtype: np.dtype, annotation_shape: Tuple
    ) -> AnnotationZarrArray:
        """
        Get the array for the given image resolution and annotation dtype.

        Args:
            annotation_dtype: The numpy dtype (uint8, uint16, uint32, uint64)
            annotation_shape: Tuple of spatial dimensions (H, W, D?)

        Returns:
            AnnotationZarrArray instance

        Raises:
            FileNotFoundError: If the array does not exist
        """
        array_name = self._get_array_name(annotation_dtype, annotation_shape)

        array_shape = (0,) + annotation_shape
        group = self.root.require_group(group_name)

        array = group.get(array_name, None)

        print(f"array_name: {array_name}")

        if array is None:
            array = group.create_array(
                name=array_name,
                shape=array_shape,
                chunks=(1, *annotation_shape),
                dtype=annotation_dtype,
                overwrite=False,
            )

        return AnnotationZarrArray(array)

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
        
        # Check if only one of axis or slice_index is provided
        if (axis is not None) != (slice_index is not None):
            raise ValueError("Both axis and slice_index must be provided together for slice operations")
        
        # If both axis and slice_index are provided, read a slice
        if axis is not None and slice_index is not None:
            return zarr_array.read_slice(zarr_index, axis, slice_index)
        # Otherwise, read the full annotation
        else:
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
        # get the array
        zarr_array = self.get_array(group_name, data_dtype, data_shape)

        # Check if only one of axis or slice_index is provided
        if (axis is not None) != (slice_index is not None):
            raise ValueError("Both axis and slice_index must be provided together for slice operations")

        # If both axis and slice_index are provided, write a slice
        if axis is not None and slice_index is not None:
            if zarr_index is None:
                raise ValueError("zarr_index must be provided for slice writes")
            zarr_array.write_slice(zarr_index, axis, slice_index, data)
            return zarr_index
        # Otherwise, write the full annotation
        else:
            return zarr_array.write(zarr_index, data)
