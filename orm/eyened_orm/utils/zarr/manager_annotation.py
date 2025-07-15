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

    def defragment_to_new_store(self, new_store_path: str | Path):
        """
        Defragment the zarr store by copying all annotations to a new store with sequential ZarrArrayIndex values.
        
        This method creates a new zarr store and copies all existing annotations to it,
        assigning new sequential ZarrArrayIndex values to eliminate gaps and improve storage efficiency.
        
        Args:
            new_store_path: Path to the new zarr store
            
        Returns:
            dict: Mapping of old ZarrArrayIndex to new ZarrArrayIndex for each group and array
        """
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from eyened_orm import Annotation, DBManager
        
        # Create new zarr store manager
        new_manager = AnnotationZarrStorageManager(new_store_path)
        
        # Get database session
        session = DBManager.get_session()
        
        try:
            # Query all annotations with ZarrArrayIndex
            annotations = session.execute(
                select(Annotation)
                .where(Annotation.ZarrArrayIndex.is_not(None))
                .where(~Annotation.Inactive)
                .order_by(Annotation.AnnotationTypeID, Annotation.ZarrArrayIndex)
            ).scalars().all()
            
            print(f"Found {len(annotations)} annotations to defragment")
            
            # Track new indices for each group/array combination
            new_indices = {}
            index_mapping = {}
            
            # Process annotations in batches by group and array type
            for annotation in annotations:
                try:
                    # Get annotation data shape and type
                    group_name = str(annotation.AnnotationTypeID)
                    data_dtype = np.dtype(np.uint8)  # Default dtype for annotations
                    data_shape = annotation.shape
                    
                    # Create unique key for this array type
                    array_key = (group_name, data_dtype, *data_shape)
                    
                    # Initialize new index counter for this array type
                    if array_key not in new_indices:
                        new_indices[array_key] = 0
                        index_mapping[array_key] = {}
                    
                    # Read annotation data from old store
                    old_zarr_index = annotation.ZarrArrayIndex
                    annotation_data = self.read(
                        group_name=group_name,
                        data_dtype=data_dtype,
                        data_shape=data_shape,
                        zarr_index=old_zarr_index
                    )
                    
                    # Write to new store with new index
                    new_zarr_index = new_manager.write(
                        group_name=group_name,
                        data_dtype=data_dtype,
                        data_shape=data_shape,
                        data=annotation_data,
                        zarr_index=None  # Let it assign new index
                    )
                    
                    # Update mapping
                    index_mapping[array_key][old_zarr_index] = new_zarr_index
                    new_indices[array_key] = new_zarr_index + 1
                    
                    # Update annotation in database
                    annotation.ZarrArrayIndex = new_zarr_index
                    
                    if len(index_mapping[array_key]) % 100 == 0:
                        print(f"Processed {len(index_mapping[array_key])} annotations for array {array_key}")
                        session.commit()
                        
                except Exception as e:
                    print(f"Error processing annotation {annotation.AnnotationID}: {e}")
                    continue
            
            # Final commit
            session.commit()
            
            # Print summary
            total_copied = sum(len(mapping) for mapping in index_mapping.values())
            print(f"Successfully defragmented {total_copied} annotations")
            
            for array_key, mapping in index_mapping.items():
                print(f"Array {array_key}: {len(mapping)} annotations")
                
            return index_mapping
            
        finally:
            session.close()
