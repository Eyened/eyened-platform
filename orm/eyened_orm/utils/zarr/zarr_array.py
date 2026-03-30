from typing import Optional, Tuple

import numpy as np
import zarr


class ZarrArray:
    """Wrapper around zarr.Array used for segmentation storage."""

    def __init__(self, zarr_array: zarr.Array):
        self.array = zarr_array

    def write(self, zarr_index: Optional[int], segmentation_data: np.ndarray) -> int:
        if len(segmentation_data.shape) != 3:
            raise ValueError(
                f"Expected 3D array (D, H, W), got shape {segmentation_data.shape}"
            )

        expected_spatial = self.segmentation_shape
        actual_spatial = segmentation_data.shape
        if actual_spatial != expected_spatial:
            raise ValueError(
                f"Expected spatial dimensions {expected_spatial}, got {actual_spatial}"
            )

        if segmentation_data.dtype != self.array.dtype:
            raise ValueError(
                f"Expected dtype {self.array.dtype}, got {segmentation_data.dtype}"
            )

        if zarr_index is not None:
            if zarr_index >= self.array.shape[0]:
                raise IndexError(
                    f"Invalid zarr_index: {zarr_index}. Array length: {self.array.shape[0]}"
                )
            self.array[zarr_index, ...] = segmentation_data
            return zarr_index

        return self._append_to_array(segmentation_data)

    def _append_to_array(self, segmentation_data: np.ndarray) -> int:
        self.array.append(segmentation_data[None, ...])
        return self.array.shape[0] - 1

    def _append_zeroed_element(self) -> int:
        zero_data = np.zeros(self.segmentation_shape, dtype=self.array.dtype)
        return self._append_to_array(zero_data)

    def write_slice(
        self, zarr_index: Optional[int], axis: int, slice_index: int, slice_data: np.ndarray
    ) -> int:
        if zarr_index is None:
            zarr_index = self._append_zeroed_element()
        elif zarr_index >= self.array.shape[0]:
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {self.array.shape[0]}"
            )

        if axis not in [0, 1, 2]:
            raise ValueError(
                f"Invalid axis: {axis}. Must be 0 (depth), 1 (height), or 2 (width)"
            )

        max_slice_index = self.segmentation_shape[axis]
        if slice_index < 0 or slice_index >= max_slice_index:
            raise IndexError(
                f"Invalid slice_index: {slice_index}. Must be in range [0, {max_slice_index})"
            )

        expected_shape = list(self.segmentation_shape)
        expected_shape.pop(axis)
        if slice_data.shape != tuple(expected_shape):
            raise ValueError(
                f"Expected slice shape {tuple(expected_shape)}, got {slice_data.shape}"
            )

        if slice_data.dtype != self.array.dtype:
            raise ValueError(
                f"Expected dtype {self.array.dtype}, got {slice_data.dtype}"
            )

        slice_indices = [slice(None)] * 4
        slice_indices[0] = zarr_index
        slice_indices[axis + 1] = slice_index
        self.array[tuple(slice_indices)] = slice_data
        return zarr_index

    def read_slice(self, zarr_index: int, axis: int, slice_index: int) -> np.ndarray:
        if zarr_index is None or zarr_index >= self.array.shape[0]:
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {self.array.shape[0]}"
            )

        if axis not in [0, 1, 2]:
            raise ValueError(
                f"Invalid axis: {axis}. Must be 0 (depth), 1 (height), or 2 (width)"
            )

        max_slice_index = self.segmentation_shape[axis]
        if slice_index < 0 or slice_index >= max_slice_index:
            raise IndexError(
                f"Invalid slice_index: {slice_index}. Must be in range [0, {max_slice_index})"
            )

        slice_indices = [slice(None)] * 4
        slice_indices[0] = zarr_index
        slice_indices[axis + 1] = slice_index
        return self.array[tuple(slice_indices)]

    def read(self, zarr_index: int) -> np.ndarray:
        if zarr_index is None or zarr_index >= self.array.shape[0]:
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {self.array.shape[0]}"
            )
        return self.array[zarr_index, ...]

    @property
    def shape(self) -> Tuple[int, ...]:
        return self.array.shape

    @property
    def segmentation_shape(self) -> Tuple[int, ...]:
        return self.array.shape[1:]

    @property
    def dtype(self) -> np.dtype:
        return self.array.dtype

    @property
    def is_volume(self) -> bool:
        return all(dim > 1 for dim in self.segmentation_shape)

    def __len__(self) -> int:
        return self.array.shape[0]
