import gzip
import json
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from eyened_orm.ImageInstance import AxisEnum
from pydantic import BaseModel
import numpy as np
from PIL import Image
from sqlalchemy import JSON, Column, Index, event
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Session, validates
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (
        AnnotationData,
        AnnotationType,
        Creator,
        Feature,
        ImageInstance,
        Patient,
        Series,
        Study,
    )


# Define the mixin
class SegmentationMixin(BaseModel):
    # index in the zarr array of the annotation
    ZarrArrayIndex: int | None = None

    # for 2D or 3Dannotations of 3D volumes:
    #  - if 2D, index of the annotation along the volume axis with size=1
    #  - if 3D, list of indices of the volume with valid annotations 
    #    (the shape of the annot volume must match the image volume)
    ScanIndices: Optional[Dict[str, Any]] = Field(sa_type=JSON)
    Width: int
    Height: int
    Depth: int

    # Matrix that projects the annotation to image space
    ImageProjectionMatrix: Optional[Dict[str, Any]] = Field(sa_type=JSON)

    SparseAxis: int | None = None

class AnnotationBase(Base, SegmentationMixin):
    """
    Used for segmentation (i.e. masks)
    """

    # Patient is required, Study, Series and ImageInstance are optional
    # TODO: perhaps only ImageInstance is required and the others should be removed
    PatientID: int|None = Field(foreign_key="Patient.PatientID", default=None)
    StudyID: int | None = Field(foreign_key="Study.StudyID", default=None)
    SeriesID: int | None = Field(foreign_key="Series.SeriesID", default=None)
    ImageInstanceID: int | None = Field(
        foreign_key="ImageInstance.ImageInstanceID", ondelete="CASCADE", default=None
    )
    CreatorID: int = Field(foreign_key="Creator.CreatorID")
    FeatureID: int = Field(foreign_key="Feature.FeatureID")
    AnnotationTypeID: int = Field(foreign_key="AnnotationType.AnnotationTypeID")
    AnnotationReferenceID: int | None = Field(
        foreign_key="Annotation.AnnotationID", default=None
    )
    Inactive: bool = False

    


class Annotation(AnnotationBase, table=True):
    __tablename__ = "Annotation"

    __table_args__ = (
        Index("fk_Annotation_Creator1_idx", "CreatorID"),
        Index("fk_Annotation_Feature1_idx", "FeatureID"),
        Index("fk_Annotation_Study1_idx", "StudyID"),
        Index("fk_Annotation_ImageInstance1_idx", "ImageInstanceID"),
        Index("fk_Annotation_AnnotationType1_idx", "AnnotationTypeID"),
        Index("fk_Annotation_Patient1_idx", "PatientID"),
        Index("fk_Annotation_Series1_idx", "SeriesID"),
    )

    AnnotationID: int | None = Field(default=None, primary_key=True)

    DateInserted: datetime = Field(default_factory=datetime.now)

    Patient: Optional["Patient"] = Relationship(back_populates="Annotations")
    Study: Optional["Study"] = Relationship(back_populates="Annotations")
    Series: Optional["Series"] = Relationship(back_populates="Annotations")
    ImageInstance: Optional["ImageInstance"] = Relationship(
        back_populates="Annotations"
    )
    Creator: "Creator" = Relationship(back_populates="Annotations")
    Feature: "Feature" = Relationship(back_populates="Annotations")
    AnnotationType: "AnnotationType" = Relationship(back_populates="Annotations")
    AnnotationReference: Optional["Annotation"] = Relationship(
        back_populates="ChildAnnotations",
        sa_relationship_kwargs={"remote_side": "Annotation.AnnotationID"},
    )

    ChildAnnotations: List["Annotation"] = Relationship(
        back_populates="AnnotationReference",
        cascade_delete=True,
    )
    # Actual data is stored in AnnotationData
    AnnotationData: List["AnnotationData"] = Relationship(
        back_populates="Annotation", cascade_delete=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.SparseAxis is not None:
            if not isinstance(self.ScanIndices, list):
                raise ValueError("ScanIndices must be a list when SparseAxis is not None")

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.Height, self.Width, self.Depth)
    
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
    
    @property
    def l1_axis(self) -> AxisEnum | None:
        if self.Height == 1:
            return AxisEnum.HEIGHT
        elif self.Width == 1:
            return AxisEnum.WIDTH
        elif self.Depth == 1:
            return AxisEnum.DEPTH
        else:
            return None
    
    @property
    def projection_axis(self) -> AxisEnum | None:
        if self.is_sparse:
            return self.SparseAxis
        else:
            return self.l1_axis
        
    # check that the dimensions that are not the length 1 axis match
    @property
    def shape_matches_image_shape(self):
        image_shape = self.ImageInstance.shape
        annotation_shape = self.shape
        for i, (x,y) in enumerate(zip(image_shape, annotation_shape)):
            if i != self.l1_axis and x != y:
                return False
        return True

    @property
    def FeatureName(self):
        return self.Feature.FeatureName

    @property
    def PatientIdentifier(self):
        return self.Patient.PatientIdentifier

    @property
    def Project(self):
        return self.Patient.Project

    @property
    def ProjectName(self):
        return self.Project.ProjectName

    @property
    def numpy(self) -> Optional[np.ndarray]:
        return self.read_data()
    
    def read_data(self, axis: Optional[int] = None, slice_index: Optional[int] = None) -> np.ndarray:
        if self.ZarrArrayIndex is None:
            return None
        
        if not self.config:
            raise ValueError("Configuration not initialized")

        if not self.ImageInstance:
            raise ValueError("Annotation has no associated ImageInstance")
        
        return self.annotation_storage_manager.read(
            group_name=str(self.AnnotationTypeID),
            data_dtype=np.dtype(np.uint8),
            data_shape=self.shape,
            zarr_index=self.ZarrArrayIndex,
            axis=axis,
            slice_index=slice_index
        )

    def write_data(self, data: np.ndarray, axis: Optional[int] = None, slice_index: Optional[int] = None) -> int:
        """Write annotation data to the zarr array and update the ZarrArrayIndex."""
        if not self.config:
            raise ValueError("Configuration not initialized")

        if not self.ImageInstance:
            raise ValueError("Annotation has no associated ImageInstance")

        zarr_index = self.annotation_storage_manager.write(
            group_name=str(self.AnnotationTypeID), 
            data_dtype=np.dtype(np.uint8),
            data_shape=self.shape,
            data=data, 
            zarr_index=self.ZarrArrayIndex,
            axis=axis,
            slice_index=slice_index
        )

        # for sparse annotations, we need to update the ScanIndices list
        if self.is_sparse and axis == self.SparseAxis:
            if slice_index not in self.ScanIndices:
                # copy necessary to ensure update is picked up by the ORM
                scan_indices = self.ScanIndices.copy()
                scan_indices.append(slice_index)
                self.ScanIndices = scan_indices

        self.ZarrArrayIndex = zarr_index
        return zarr_index

    def __repr__(self):
        return f"Annotation({self.AnnotationID}, {self.FeatureName}, {self.Creator.CreatorName})"

    @classmethod
    def create(
        cls,
        instance: "ImageInstance",
        feature: "Feature",
        creator: "Creator",
        annotationType: "AnnotationType",
    ) -> "Annotation":
        a = cls()
        a.ImageInstanceID = instance.ImageInstanceID
        a.Patient = instance.Patient
        a.Study = instance.Study
        a.Series = instance.Series
        a.Creator = creator
        a.AnnotationType = annotationType
        a.Feature = feature
        a.DateInserted = datetime.now()
        return a


def load_png(filepath: Path) -> np.ndarray:
    return np.array(Image.open(filepath))


def load_binary(filepath: Path, shape) -> np.ndarray:
    ext = filepath.suffix.lower()
    if ext == ".gz":
        with gzip.open(filepath, "rb") as f:
            raw = np.frombuffer(f.read(), dtype=np.uint8)
    else:
        with open(filepath, "rb") as f:
            raw = np.frombuffer(f.read(), dtype=np.uint8)
    return raw.reshape(shape, order="C")


class AnnotationDataBase(Base):
    """
    This is used for storing the actual data of the annotation
    """

    AnnotationID: int = Field(
        foreign_key="Annotation.AnnotationID",
        ondelete="CASCADE",
        primary_key=True,
    )
    # use -1 for all scans (e.g. enface OCT)
    ScanNr: int = Field(primary_key=True)

    # AnnotationPlane: AnnotationPlane

    ValueInt: int | None
    ValueFloat: float | None
    ValueBlob: bytes | None = Field(sa_column=Column(LONGBLOB))


class AnnotationData(AnnotationDataBase, table=True):
    __tablename__ = "AnnotationData"

    __table_args__ = (Index("fk_AnnotationData_Annotation1_idx", "AnnotationID"),)
    Annotation: "Annotation" = Relationship(back_populates="AnnotationData")

    DatasetIdentifier: str | None = Field(max_length=45, unique=True, nullable=True)
    DateModified: datetime | None = Field(
        default_factory=datetime.now, sa_column_kwargs={"onupdate": datetime.now}
    )

    @classmethod
    def create(
        cls,
        annotation: "Annotation",
        # file_extension: str = "png",
        scan_nr: int = 0,
        annotation_plane: str = "PRIMARY",
    ) -> "AnnotationData":
        annotation_data = cls()
        annotation_data.Annotation = annotation
        annotation_data.ScanNr = scan_nr
        annotation_data.AnnotationPlane = AnnotationPlane[annotation_plane]

        return annotation_data

    @classmethod
    def by_composite_id(
        cls, session: Session, annotation_data_id: str
    ) -> "AnnotationData":
        """
        Get an AnnotationData object from a composite ID string separated by an underscore.
        (AnnotationID_ScanNr)
        """
        annotation_id, scan_nr = map(int, annotation_data_id.split("_"))
        return cls.by_pk(session, (annotation_id, scan_nr))

    def get_default_path(self, ext: str) -> str:
        a = self.Annotation
        return f"{a.Patient.PatientID}/{a.AnnotationID}_{self.ScanNr}.{ext}"

    @property
    def path(self) -> Path:
        if not self.config:
            raise ValueError("Configuration not initialized")
        return Path(self.config.annotations_path) / self.DatasetIdentifier

    @property
    def trash_path(self) -> Path:
        if not self.config:
            raise ValueError("Configuration not initialized")
        return Path(self.config.trash_path) / self.DatasetIdentifier

    def load_data(self) -> Any:
        """Load the annotation data from the file."""
        if self.MediaType == "image/png":
            return load_png(self.path)
        elif self.MediaType == "application/octet-stream":
            instance = self.Annotation.ImageInstance
            return load_binary(self.path, (instance.Rows_y, instance.Columns_x))
        else:
            raise ValueError(f"Unsupported media type {self.MediaType}")

    def get_mask(self, mask_type: str = "segmentation") -> np.ndarray:
        """
        Returns a mask based on the specified type ('segmentation' or 'questionable').

        Args:
            mask_type (str): The type of mask to return. Options are 'segmentation' or 'questionable'.

        Returns:
            np.ndarray: A 2D boolean mask.

        Raises:
            ValueError: If the annotation type is unsupported or the mask type is invalid.
        """
        data = self.load_data()
        data_representation = self.Annotation.AnnotationType.DataRepresentation

        if data_representation == DataRepresentation.RG_MASK:
            assert len(data.shape) == 3, "Expected color image"
            if mask_type == "segmentation":
                return data[:, :, 0] > 0  # red channel
            elif mask_type == "questionable":
                return data[:, :, 1] > 0  # green channel
            else:
                raise ValueError(f"Unsupported mask type: {mask_type}")

        elif data_representation == DataRepresentation.BINARY:
            assert len(data.shape) == 2, "Expected grayscale image"
            return data > 0
        else:
            raise ValueError(f"Unsupported annotation type {data_representation}")

    @property
    def segmentation_mask(self) -> np.ndarray:
        return self.get_mask("segmentation")

    @property
    def questionable_mask(self) -> np.ndarray:
        return self.get_mask("questionable")



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
    R8 = "R8" # 8-bit unsigned integer, interpreted as [0, 1]
    R8UI = "R8UI" # 8-bit unsigned integer
    R16UI = "R16UI" # 16-bit unsigned integer
    R32UI = "R32UI" # 32-bit unsigned integer
    R32F = "R32F" # 32-bit float

class AnnotationTypeBase(Base):
    AnnotationTypeName: str = Field(max_length=45)
    DataRepresentation: DataRepresentation
    DataType: Datatype


class AnnotationType(AnnotationTypeBase, table=True):
    __tablename__ = "AnnotationType"
    _name_column: ClassVar[str] = "AnnotationTypeName"

    AnnotationTypeID: int = Field(primary_key=True)

    Annotations: List["Annotation"] = Relationship(back_populates="AnnotationType")


class FeatureBase(Base):
    FeatureName: str = Field(max_length=60, unique=True)


class Feature(FeatureBase, table=True):
    __tablename__ = "Feature"
    _name_column: ClassVar[str] = "FeatureName"

    FeatureID: int | None = Field(default=None, primary_key=True)

    Annotations: List["Annotation"] = Relationship(back_populates="Feature")
    DateInserted: datetime = Field(default_factory=datetime.now)


class AnnotationTypeFeature(Base, table=True):
    __tablename__ = "AnnotationTypeFeature"
    __table_args__ = (
        Index("fk_AnnotationTypeFeature_AnnotationType1_idx", "AnnotationTypeID"),
        Index("fk_AnnotationTypeFeature_Feature1_idx", "FeatureID"),
    )

    AnnotationTypeID: int = Field(
        foreign_key="AnnotationType.AnnotationTypeID", primary_key=True
    )
    FeatureID: int = Field(foreign_key="Feature.FeatureID", primary_key=True)
    FeatureIndex: int = Field(primary_key=True)

