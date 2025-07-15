from typing import Optional, Tuple

import numpy as np
import zarr


class AnnotationZarrArray:
    """
    A wrapper class for zarr arrays used to store annotation data.

    Arrays are of shape (N, H, W, D) where:
    - N is the size of the annotation index dimension
    - H, W, D are spatial dimensions (any can be 1 for 2D data, all >1 for 3D data)

    Usage:
        # Load existing array
        array = AnnotationZarrArray("path/to/existing/array.zarr")

        # Create new array
        array = AnnotationZarrArray.create_new("path/to/new/array.zarr", "binary_mask", (512, 512))
    """

    def __init__(self, zarr_array: zarr.Array):
        """
        Initialize the AnnotationZarrArray from an existing array.

        Args:
            zarr_path: Path to the zarr array on disk

        Raises:
            FileNotFoundError: If the zarr array does not exist on disk
            ValueError: If the array shape is invalid
        """
        self.array = zarr_array

    def write(self, zarr_index: Optional[int], annot_data: np.ndarray) -> int:
        """
        Write annotation data to the zarr array.

        Args:
            zarr_index: Index in the array where to write. If None or >= len(A), append to array.
            annot_data: Annotation data as numpy array of shape (H, W, D) where any spatial dimension can be 1 for 2D images

        Returns:
            The zarr_index where data was written
        """
        # Validate input data shape - annot_data should be (H, W, D)
        if len(annot_data.shape) != 3:
            raise ValueError(
                f"Expected 3D array (H, W, D), got shape {annot_data.shape}"
            )

        # Check if spatial dimensions match
        expected_spatial = self.annotation_resolution
        actual_spatial = annot_data.shape  # H, W, D
        if actual_spatial != expected_spatial:
            raise ValueError(
                f"Expected spatial dimensions {expected_spatial}, got {actual_spatial}"
            )

        # Validate data type
        if annot_data.dtype != self.array.dtype:
            raise ValueError(
                f"Expected dtype {self.array.dtype}, got {annot_data.dtype}"
            )

        if zarr_index is not None and zarr_index < self.array.shape[0]:
            
            # Write to existing index
            self.array[zarr_index, ...] = annot_data
            return zarr_index
        else:
            # Append to array
            self.array.append(annot_data[None, ...])
            return self.array.shape[0] - 1

    def write_slice(self, zarr_index: int, axis: int, slice_index: int, slice_data: np.ndarray) -> None:
        """
        Write a slice of annotation data to the zarr array.

        Args:
            zarr_index: Index in the array where to write the slice
            axis: Axis along which to write the slice (0=height, 1=width, 2=depth)
            slice_index: Index along the specified axis
            slice_data: Slice data as numpy array of shape (H', W') where H' and W' depend on the axis

        Raises:
            IndexError: If zarr_index or slice_index is invalid
            ValueError: If axis is invalid or slice_data dimensions don't match
        """
        if zarr_index is None or zarr_index >= self.array.shape[0]:
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {self.array.shape[0]}"
            )

        if axis not in [0, 1, 2]:
            raise ValueError(f"Invalid axis: {axis}. Must be 0 (height), 1 (width), or 2 (depth)")

        # Check if the array is volumetric (all spatial dimensions > 1)
        if not self.is_volume:
            raise ValueError("write_slice is only supported for volumetric annotations (all spatial dimensions > 1)")

        # Validate slice_index
        max_slice_index = self.annotation_resolution[axis]
        if slice_index < 0 or slice_index >= max_slice_index:
            raise IndexError(
                f"Invalid slice_index: {slice_index}. Must be in range [0, {max_slice_index})"
            )

        # Validate slice_data shape
        expected_shape = list(self.annotation_resolution)
        expected_shape.pop(axis)  # Remove the axis dimension
        
        if slice_data.shape != tuple(expected_shape):
            raise ValueError(
                f"Expected slice shape {tuple(expected_shape)}, got {slice_data.shape}"
            )

        # Validate data type
        if slice_data.dtype != self.array.dtype:
            raise ValueError(
                f"Expected dtype {self.array.dtype}, got {slice_data.dtype}"
            )

        # Create the slice index
        slice_indices = [slice(None)] * 4  # [zarr_index, height, width, depth]
        slice_indices[0] = zarr_index
        slice_indices[axis + 1] = slice_index  # +1 because zarr_index is at index 0

        # Write the slice
        self.array[tuple(slice_indices)] = slice_data

    def read_slice(self, zarr_index: int, axis: int, slice_index: int) -> np.ndarray:
        """
        Read a slice of annotation data from the zarr array.

        Args:
            zarr_index: Index in the array to read the slice from
            axis: Axis along which to read the slice (0=height, 1=width, 2=depth)
            slice_index: Index along the specified axis

        Returns:
            Slice data as numpy array of shape (H', W') where H' and W' depend on the axis

        Raises:
            IndexError: If zarr_index or slice_index is invalid
            ValueError: If axis is invalid
        """
        if zarr_index is None or zarr_index >= self.array.shape[0]:
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {self.array.shape[0]}"
            )

        if axis not in [0, 1, 2]:
            raise ValueError(f"Invalid axis: {axis}. Must be 0 (height), 1 (width), or 2 (depth)")

        # Check if the array is volumetric (all spatial dimensions > 1)
        if not self.is_volume:
            raise ValueError("read_slice is only supported for volumetric annotations (all spatial dimensions > 1)")

        # Validate slice_index
        max_slice_index = self.annotation_resolution[axis]
        if slice_index < 0 or slice_index >= max_slice_index:
            raise IndexError(
                f"Invalid slice_index: {slice_index}. Must be in range [0, {max_slice_index})"
            )

        # Create the slice index
        slice_indices = [slice(None)] * 4  # [zarr_index, height, width, depth]
        slice_indices[0] = zarr_index
        slice_indices[axis + 1] = slice_index  # +1 because zarr_index is at index 0

        # Read the slice
        return self.array[tuple(slice_indices)]

    def read(self, zarr_index: int) -> np.ndarray:
        """
        Read annotation data from the zarr array.

        Args:
            zarr_index: Index in the array to read from

        Returns:
            Annotation data as numpy array

        Raises:
            IndexError: If zarr_index is invalid
        """
        if zarr_index is None or zarr_index >= self.array.shape[0]:
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {self.array.shape[0]}"
            )

        return self.array[zarr_index, ...]

    def delete(self, zarr_index: int) -> None:
        """
        Delete annotation data from the zarr array by clearing the specified index.

        Args:
            zarr_index: Index in the array to delete

        Raises:
            IndexError: If zarr_index is invalid
        """
        if zarr_index is None or zarr_index >= self.array.shape[0]:
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {self.array.shape[0]}"
            )

        # Clear the data at the specified index
        # For boolean arrays, set to False; for others, set to 0
        if self.array.dtype == np.bool_:
            self.array[zarr_index, ...] = False
        else:
            self.array[zarr_index, ...] = 0

    @property
    def shape(self) -> Tuple[int, ...]:
        """Get the shape of the zarr array."""
        return self.array.shape

    @property
    def annotation_resolution(self) -> Tuple[int, ...]:
        """Get the spatial resolution of the zarr array."""
        return self.array.shape[1:]

    @property
    def dtype(self) -> np.dtype:
        """Get the data type of the zarr array."""
        return self.array.dtype

    @property
    def is_volume(self) -> bool:
        """Check if the annotation is volumetric (all spatial dimensions > 1)."""
        return all(dim > 1 for dim in self.annotation_resolution)

    @property
    def metadata(self) -> dict:
        pass

    def __len__(self) -> int:
        """Get the number of annotations in the array."""
        return self.array.shape[0]
