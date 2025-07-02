from pathlib import Path
from typing import Tuple

import numpy as np
import zarr

from .annotation_array import AnnotationZarrArray


class AnnotationZarrStorageManager:
    """
    A manager class for creating and managing zarr arrays for annotation data.

    This class handles the creation, existence checking, and retrieval of zarr arrays
    based on annotation types and image shapes. Arrays are stored with names that
    encode the annotation type and image dimensions.
    """

    def __init__(self, basepath: str | Path):
        """
        Initialize the storage manager.

        Args:
            basepath: Base path where zarr arrays will be stored
        """
        self.basepath = Path(basepath)
        self.basepath.mkdir(parents=True, exist_ok=True)

    def _get_array_name(self, annotation_type, annotation_shape: Tuple) -> str:
        """
        Generate the array name based on annotation type and image shape.

        Args:
            annotation_type: The AnnotationType object
            annotation_shape: Tuple of spatial dimensions (H, W, D?)

        Returns:
            Array name in format <AnnotationTypeName>_<H_W_D?>.zarr
        """
        # Convert image shape to string representation
        shape_str = "_".join(str(dim) for dim in annotation_shape)
        return f"{annotation_type.AnnotationTypeName}_{shape_str}.zarr"

    def _get_array_path(self, annotation_type, annotation_shape: Tuple) -> Path:
        """
        Get the full path for the zarr array.

        Args:
            annotation_type: The AnnotationType object
            annotation_shape: Tuple of spatial dimensions (H, W, D?)

        Returns:
            Full path to the zarr array
        """
        array_name = self._get_array_name(annotation_type, annotation_shape)
        return self.basepath / array_name

    def _get_dtype_and_channels(self, annotation_type) -> Tuple[np.dtype, int]:
        """
        Determine the data type and number of channels based on annotation type interpretation.

        Args:
            annotation_type: The AnnotationType object

        Returns:
            Tuple of (dtype, num_channels)
        """
        interpretation = annotation_type.Interpretation

        if interpretation == "Binary mask":
            return np.bool_, 1
        elif interpretation == "R/G mask":
            return np.bool_, 2  # Red channel for segmentation, Green for questionable
        elif interpretation == "Label numbers":
            return np.uint8, 1
        elif interpretation == "Layer bits":
            return np.uint16, 1
        elif interpretation == "Probability":
            return np.float32, 1
        else:
            raise ValueError(f"Unsupported annotation interpretation: {interpretation}")

    def create_array(
        self, annotation_type, annotation_shape: Tuple
    ) -> AnnotationZarrArray:
        """
        Create an empty zarr array for the given image resolution and annotation type.

        Args:
            annotation_type: The AnnotationType object
            annotation_shape: Tuple of spatial dimensions (H, W, D?)

        Returns:
            AnnotationZarrArray instance

        Raises:
            FileExistsError: If the array already exists
            ValueError: If the annotation type interpretation is unsupported
        """
        array_path = self._get_array_path(annotation_type, annotation_shape)

        if array_path.exists():
            raise FileExistsError(f"Zarr array already exists at {array_path}")

        # Determine data type and channel count
        dtype, num_channels = self._get_dtype_and_channels(annotation_type)

        # Create the array shape: (0, H, W, D?, C)
        # Start with 0 annotations, add spatial dimensions, then channels
        array_shape = (0,) + annotation_shape + (num_channels,)

        # Create the zarr array
        array = zarr.create(
            array_shape, dtype=dtype, store=str(array_path), overwrite=False
        )

        # Return the wrapper
        return AnnotationZarrArray(str(array_path))

    def array_exists(self, annotation_type, annotation_shape: Tuple) -> bool:
        """
        Check if an array exists suitable for this type of data.

        Args:
            annotation_type: The AnnotationType object
            annotation_shape: Tuple of spatial dimensions (H, W, D?)

        Returns:
            True if the array exists, False otherwise
        """
        array_path = self._get_array_path(annotation_type, annotation_shape)
        return array_path.exists()

    def get_array(
        self, annotation_type, annotation_shape: Tuple
    ) -> AnnotationZarrArray:
        """
        Get the array for the given image resolution and annotation type.

        Args:
            annotation_type: The AnnotationType object
            annotation_shape: Tuple of spatial dimensions (H, W, D?)

        Returns:
            AnnotationZarrArray instance

        Raises:
            FileNotFoundError: If the array does not exist
        """
        array_path = self._get_array_path(annotation_type, annotation_shape)

        if not array_path.exists():
            raise FileNotFoundError(f"Zarr array not found at {array_path}")

        return AnnotationZarrArray(str(array_path))
