from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional

import numpy as np
from sqlalchemy import JSON, Index
from sqlmodel import Field, Relationship

from .base import Base


class DataRepresentation(Enum):
    # 0 = background, >0 = foreground
    Binary = "Binary"

    # A binary mask with two channels packed into a single byte.
    # Bit 0 = mask; Bit 1 = questionable/uncertain.
    DualBitMask = "DualBitMask"

    # Per-pixel float mask (soft segmentation, probability map)
    Probability = "Probability"

    # Multi-label segmentation — each bit in an integer represents a label.
    # For example:
    #   0x00 => 00000000 => background
    #   0x01 => 00000001 => feature 1 present
    #   0x02 => 00000010 => feature 2 present
    #   0x04 => 00000100 => feature 3 present
    #   0x03 => 00000011 => feature 1 + feature 2 present
    MultiLabel = "MultiLabel"

    # Multi-class segmentation — each voxel/pixel is assigned exactly one class.
    # For example:
    #   0 = background
    #   1 = ILM
    #   2 = GCL
    #   3 = IPL
    #   ...
    MultiClass = "MultiClass"


class Datatype(Enum):
    R8 = "R8"  # 8-bit unsigned integer, interpreted as [0, 1]
    R8UI = "R8UI"  # 8-bit unsigned integer
    R16UI = "R16UI"  # 16-bit unsigned integer
    R32UI = "R32UI"  # 32-bit unsigned integer
    R32F = "R32F"  # 32-bit float


class SegmentationBase(Base):
    # index in the zarr array of the segmentation
    ZarrArrayIndex: int | None = None

    # image instance that the segmentation is associated with
    ImageInstanceID: int | None = Field(
        foreign_key="ImageInstance.ImageInstanceID", ondelete="CASCADE", default=None
    )

    # shape of the segmentation
    Depth: int
    Height: int
    Width: int

    # indicates the axis along which the segmentation is sparse
    # axis 0 = depth, axis 1 = height, axis 2 = width
    SparseAxis: int | None = None

    # Matrix that projects the segmentation to image space (along the sparse axis)
    # If None, the shape of the segmentation must match the shape of the image instance
    ImageProjectionMatrix: List[List[float]] | None = Field(sa_type=JSON, default=None)

    # indices with valid segmentation data along the sparse axis
    # If None, the segmentation is dense (i.e valid for all ScanIndices)
    ScanIndices: List[int] | None = Field(sa_type=JSON, default=None)

    DataRepresentation: DataRepresentation
    DataType: Datatype

    Threshold: float = Field(default=0.5)
    ReferenceSegmentationID: int | None = Field(foreign_key="Segmentation.SegmentationID", default=None)

    @property
    def dtype(self) -> np.dtype:
        if self.DataType == Datatype.R8:
            return np.dtype(np.uint8)
        elif self.DataType == Datatype.R8UI:
            return np.dtype(np.uint8)
        elif self.DataType == Datatype.R16UI:
            return np.dtype(np.uint16)
        elif self.DataType == Datatype.R32UI:
            return np.dtype(np.uint32)
        elif self.DataType == Datatype.R32F:
            return np.dtype(np.float32)
        else:
            raise ValueError(f"Unsupported data type: {self.DataType}")

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.Depth, self.Height, self.Width)
   
    @property
    def is_3d(self) -> bool:
        # all axes must be > 1 in length
        return self.Height > 1 and self.Width > 1 and self.Depth > 1
    
    @property
    def is_2d(self) -> bool:
        return not self.is_3d
    
    @property
    def is_sparse(self) -> bool:
        return self.SparseAxis is not None
    
    def write_data(self, data: np.ndarray, axis: Optional[int] = None, slice_index: Optional[int] = None) -> int:
        """Write annotation data to the zarr array and update the ZarrArrayIndex."""
        if not self.config:
            raise ValueError("Configuration not initialized")

        if not self.ImageInstance:
            raise ValueError("Segmentation has no associated ImageInstance")

        zarr_index = self.annotation_storage_manager.write(
            group_name=str(self.DataRepresentation),  
            data_dtype=self.dtype,
            data_shape=self.shape,
            data=data, 
            zarr_index=self.ZarrArrayIndex,
            axis=axis,
            slice_index=slice_index
        )

        # for sparse annotations, we need to update the ScanIndices list
        if self.ScanIndices is not None and self.is_sparse and axis == self.SparseAxis:
            if slice_index not in self.ScanIndices:
                # copy necessary to ensure update is picked up by the ORM
                scan_indices = self.ScanIndices.copy()
                scan_indices.append(slice_index)
                self.ScanIndices = scan_indices

        self.ZarrArrayIndex = zarr_index
        return zarr_index

    def read_data(self, axis: Optional[int] = None, slice_index: Optional[int] = None) -> np.ndarray:
        if self.ZarrArrayIndex is None:
            return None
        
        if not self.config:
            raise ValueError("Configuration not initialized")

        if not self.ImageInstance:
            raise ValueError("Annotation has no associated ImageInstance")
        
        return self.annotation_storage_manager.read(
            group_name=str(self.DataRepresentation),
            data_dtype=self.dtype,
            data_shape=self.shape,
            zarr_index=self.ZarrArrayIndex,
            axis=axis,
            slice_index=slice_index
        )
    
class Segmentation(SegmentationBase, table=True):

    __tablename__ = "Segmentation"
    SegmentationID: int = Field(primary_key=True)

    CreatorID: int = Field(foreign_key="Creator.CreatorID")
    # feature that the segmentation represents
    FeatureID: int = Field(foreign_key="Feature.FeatureID")

    DateInserted: datetime = Field(default_factory=datetime.now)
    DateModified: datetime | None = Field(default=None)

    Inactive: bool = False


    ImageInstance: Optional["ImageInstance"] = Relationship(
        back_populates="Segmentations"
    )
    Creator: "Creator" = Relationship(back_populates="Segmentations")
    Feature: "Feature" = Relationship(back_populates="Segmentations")


class SegmentationModel(SegmentationBase, table=True):
    __tablename__ = "SegmentationModel"    
    SegmentationID: int = Field(primary_key=True)

    ModelID: int = Field(foreign_key="Model.ModelID")

    DateInserted: datetime = Field(default_factory=datetime.now)


class CompositeFeature(Base, table=True):
    __tablename__ = "CompositeFeature"
    __table_args__ = (
        Index("fk_CompositeFeature_ParentFeature1_idx", "ParentFeatureID"),
        Index("fk_CompositeFeature_ChildFeature1_idx", "ChildFeatureID"),
    )

    ParentFeatureID: int = Field(foreign_key="Feature.FeatureID", primary_key=True)
    ChildFeatureID: int = Field(foreign_key="Feature.FeatureID", primary_key=True)
    FeatureIndex: int = Field(primary_key=True)