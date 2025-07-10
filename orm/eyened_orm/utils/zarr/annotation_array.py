from typing import Optional, Tuple

import numpy as np
import zarr


class AnnotationZarrArray:
    """
    A wrapper class for zarr arrays used to store annotation data.

    Arrays are of shape (N, H, W, D?, C) where:
    - N is the size of the annotation index dimension
    - H, W, D are spatial dimensions (D is optional for 2D data)
    - C is the channel dimension determined by annotation_type

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
            annot_data: Annotation data as numpy array of shape (H, W, D, C) where D may be 1 for 2D images

        Returns:
            The zarr_index where data was written
        """
        # Validate input data shape - annot_data should be (H, W, D, C)
        if len(annot_data.shape) != 4:
            raise ValueError(
                f"Expected 4D array (H, W, D, C), got shape {annot_data.shape}"
            )

        # Check if spatial dimensions match
        expected_spatial = self.annotation_resolution
        actual_spatial = annot_data.shape[:3]  # H, W, D
        if actual_spatial != expected_spatial:
            raise ValueError(
                f"Expected spatial dimensions {expected_spatial}, got {actual_spatial}"
            )

        # Check if channel dimension matches
        expected_channels = self.array.shape[-1]
        actual_channels = annot_data.shape[-1]
        if actual_channels != expected_channels:
            raise ValueError(
                f"Expected {expected_channels} channels, got {actual_channels}"
            )

        # Validate data type
        if annot_data.dtype != self.array.dtype:
            raise ValueError(
                f"Expected dtype {self.array.dtype}, got {annot_data.dtype}"
            )

        if zarr_index is not None and zarr_index < len(self.array):
            # Write to existing index
            self.array[zarr_index, ...] = annot_data
            return zarr_index
        else:
            # Append to array
            self.array.append(annot_data[None, ...])
            return self.array.shape[0] - 1

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
        if zarr_index is None or zarr_index >= len(self.array):
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {len(self.array)}"
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
        if zarr_index is None or zarr_index >= len(self.array):
            raise IndexError(
                f"Invalid zarr_index: {zarr_index}. Array length: {len(self.array)}"
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
        return self.array.shape[1:-1]

    @property
    def num_channels(self) -> int:
        """Get the number of channels in the zarr array."""
        return self.array.shape[-1]

    @property
    def dtype(self) -> np.dtype:
        """Get the data type of the zarr array."""
        return self.array.dtype

    @property
    def metadata(self) -> dict:
        pass

    def __len__(self) -> int:
        """Get the number of annotations in the array."""
        return len(self.array)
