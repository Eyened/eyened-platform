from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import zarr

from .zarr_array import ZarrArray


class ZarrStorageManager:
    """
    A singleton manager class for creating and managing zarr arrays for segmentation data.

    This class handles the creation, existence checking, and retrieval of zarr arrays
    based on segmentation dtypes and image shapes. Arrays are stored with names that
    encode the segmentation dtype and image dimensions.
    """

    def __init__(self, store_path: str | Path):
        self.root = zarr.open_group(store=store_path, mode="a")
        self._open_arrays: Dict[Tuple, ZarrArray] = {}

    def _get_array_name(
        self, dtype: np.dtype, shape: Tuple
    ) -> str:
        shape_str = "_".join(str(dim) for dim in shape)
        return f"{str(dtype)}_{shape_str}.zarr"

    def _get_array_key(
        self, group_name: str, dtype: np.dtype, shape: Tuple
    ) -> Tuple:
        return (group_name, dtype, *shape)

    def get_array(
        self, group_name: str, dtype: np.dtype, shape: Tuple
    ) -> ZarrArray:
        """
        Get the array for the given image resolution and segmentation dtype.

        Args:
            dtype: The numpy dtype (uint8, uint16, uint32, uint64)
            shape: Tuple of spatial dimensions (D, H, W)

        Returns:
            ZarrArray instance

        Raises:
            FileNotFoundError: If the array does not exist
        """
        array_name = self._get_array_name(dtype, shape)

        array_shape = (0,) + shape
        group = self.root.require_group(group_name)

        array = group.get(array_name, None)

        print(f"array_name: {array_name}")

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
        
        # Check if only one of axis or slice_index is provided
        if (axis is not None) != (slice_index is not None):
            raise ValueError("Both axis and slice_index must be provided together for slice operations")
        
        # If both axis and slice_index are provided, read a slice
        if axis is not None and slice_index is not None:
            return zarr_array.read_slice(zarr_index, axis, slice_index)
        # Otherwise, read the full segmentation
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

        if len(data.shape) == 2 and slice_index is None:
            # case for enface projections
            if axis is None:
                raise ValueError("axis must be provided for 2D writes")
            
            # write to slice 0 in the array (but in the database it is stored as NULL)
            slice_index = 0
            

        # Check if only one of axis or slice_index is provided
        if (axis is not None) != (slice_index is not None):
            raise ValueError("Both axis and slice_index must be provided together for slice operations")

        # If both axis and slice_index are provided, write a slice
        if axis is not None and slice_index is not None:
            return zarr_array.write_slice(zarr_index, axis, slice_index, data)
        # Otherwise, write the full segmentation
        else:
            return zarr_array.write(zarr_index, data)

    def defragment_to_new_store(self, new_store_path: str | Path):
        """
        Defragment the zarr store by copying all segmentations to a new store with sequential ZarrArrayIndex values.
        
        This method creates a new zarr store and copies all existing segmentations to it,
        assigning new sequential ZarrArrayIndex values to eliminate gaps and improve storage efficiency.
        
        Args:
            new_store_path: Path to the new zarr store
            
        Returns:
            dict: Mapping of old ZarrArrayIndex to new ZarrArrayIndex for each group and array
        """
        from sqlalchemy import select
        from eyened_orm import Segmentation, DBManager
        
        # Create new zarr store manager
        new_manager = ZarrStorageManager(new_store_path)
        
        # Get database session
        session = DBManager.get_session()
        
        try:
            # Query all segmentations with ZarrArrayIndex
            segmentations = session.execute(
                select(Segmentation)
                .where(Segmentation.ZarrArrayIndex.is_not(None))
                .where(~Segmentation.Inactive) # TODO: why filter out Inactive segmentations?
                .order_by(Segmentation.SegmentationTypeID, Segmentation.ZarrArrayIndex)
            ).scalars().all()
            
            print(f"Found {len(segmentations)} segmentations to defragment")
            
            # Track new indices for each group/array combination
            new_indices = {}
            index_mapping = {}
            
            # Process segmentations in batches by group and array type
            for segmentation in segmentations:
                try:
                    # Get segmentation data shape and type
                    group_name = str(segmentation.SegmentationTypeID)
                    data_dtype = segmentation.dtype
                    data_shape = segmentation.shape
                    
                    # Create unique key for this array type
                    array_key = (group_name, data_dtype, *data_shape)
                    
                    # Initialize new index counter for this array type
                    if array_key not in new_indices:
                        new_indices[array_key] = 0
                        index_mapping[array_key] = {}
                    
                    # Read segmentation data from old store
                    old_zarr_index = segmentation.ZarrArrayIndex
                    segmentation_data = self.read(
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
                        data=segmentation_data,
                        zarr_index=None  # Let it assign new index
                    )
                    
                    # Update mapping
                    index_mapping[array_key][old_zarr_index] = new_zarr_index
                    new_indices[array_key] = new_zarr_index + 1
                    
                    # Update segmentation in database
                    segmentation.ZarrArrayIndex = new_zarr_index
                    
                    if len(index_mapping[array_key]) % 100 == 0:
                        print(f"Processed {len(index_mapping[array_key])} segmentations for array {array_key}")
                        session.commit()
                        
                except Exception as e:
                    print(f"Error processing segmentation {segmentation.SegmentationID}: {e}")
                    continue
            
            # Final commit
            session.commit()
            
            # Print summary
            total_copied = sum(len(mapping) for mapping in index_mapping.values())
            print(f"Successfully defragmented {total_copied} segmentations")
            
            for array_key, mapping in index_mapping.items():
                print(f"Array {array_key}: {len(mapping)} segmentations")
                
            return index_mapping
            
        finally:
            session.close()
