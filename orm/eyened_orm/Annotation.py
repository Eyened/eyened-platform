import gzip
import json
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, List, Optional

import numpy as np
from PIL import Image
from sqlalchemy import Column, Index, event
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Session
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


class AnnotationBase(Base):
    """
    Used for segmentation (i.e. masks)
    """

    # Patient is required, Study, Series and ImageInstance are optional
    # TODO: perhaps only ImageInstance is required and the others should be removed
    PatientID: int = Field(foreign_key="Patient.PatientID")
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

    Patient: "Patient" = Relationship(back_populates="Annotations")
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


class AnnotationPlane(Enum):
    PRIMARY = 0  # 2D images, or B-scan
    SECONDARY = 1  # Enface OCT
    TERTIARY = 2  # Across B-scans
    VOLUME = 3  # Volume OCT


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

    AnnotationPlane: AnnotationPlane

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
        annotation_plane: str = "PRIMARY"
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
        return self.config.annotations_path / self.DatasetIdentifier

    @property
    def trash_path(self) -> Path:
        if not self.config:
            raise ValueError("Configuration not initialized")
        return self.config.trash_path / self.DatasetIdentifier

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
        if self.Annotation.AnnotationType.Interpretation == "R/G mask":
            assert len(data.shape) == 3, "Expected color image"
            if mask_type == "segmentation":
                return data[:, :, 0] > 0  # red channel
            elif mask_type == "questionable":
                return data[:, :, 1] > 0  # green channel
            else:
                raise ValueError(f"Unsupported mask type: {mask_type}")

        elif self.Annotation.AnnotationType.Interpretation == "Binary mask":
            assert len(data.shape) == 2, "Expected grayscale image"
            return data > 0
        else:
            raise ValueError(
                f"Unsupported annotation type {self.Annotation.AnnotationType.Interpretation}"
            )

    @property
    def segmentation_mask(self) -> np.ndarray:
        return self.get_mask("segmentation")

    @property
    def questionable_mask(self) -> np.ndarray:
        return self.get_mask("questionable")


def move_file_to_trash(annotation_data: AnnotationData) -> None:
    """Moves a file to trash folder and stores metadata alongside it."""
    source_path = annotation_data.path
    if not source_path.exists():
        print(f"File {source_path} does not exist, skipping trash move")
        return

    trash_path = annotation_data.trash_path

    try:
        shutil.move(str(source_path), str(trash_path))
        print(f"File moved to trash: {trash_path}")

        with open(f"{trash_path}.metadata.json", "w") as f:
            json.dump(
                {
                    "annotation": annotation_data.Annotation.to_dict(),
                    "annotation_data": annotation_data.to_dict(),
                    "deleted_at": datetime.now().isoformat(),
                    "source_path": str(source_path),
                    "trash_path": str(trash_path),
                },
                f,
            )

    except Exception as e:
        print(f"Error moving file {source_path} to trash: {e}")


# Track deleted AnnotationData objects
@event.listens_for(Session, "before_flush")
def receive_before_flush(session, flush_context, instances):
    """Track AnnotationData objects being deleted before they're removed from the session."""

    deleted_annotation_data = [
        obj for obj in session.deleted if isinstance(obj, AnnotationData)
    ]
    if not deleted_annotation_data:
        return

    try:
        session.deleted_annotation_data_info = [
            {
                "path": str(obj.path),
                "trash_path": str(obj.trash_path),
                "annotation": obj.Annotation.to_dict(),
                "annotation_data": obj.to_dict(),
            }
            for obj in deleted_annotation_data
        ]
    except Exception as e:
        print(f"Error tracking deleted annotation data: {e}")


@event.listens_for(Session, "after_commit")
def receive_after_commit(session):
    """Process tracked deleted annotation data after the transaction is committed."""

    if not hasattr(session, "deleted_annotation_data_info"):
        return
    for info in session.deleted_annotation_data_info:
        try:
            source_path = Path(info["path"])
            trash_path = Path(info["trash_path"])

            if source_path.exists():
                # Create trash directory if it doesn't exist
                trash_path.parent.mkdir(parents=True, exist_ok=True)

                # Move the file to trash
                shutil.move(str(source_path), str(trash_path))
                print(f"File moved to trash: {trash_path}")

                # Store metadata
                with open(f"{trash_path}.metadata.json", "w") as f:
                    json.dump(
                        {
                            "annotation": info["annotation"],
                            "annotation_data": info["annotation_data"],
                            "deleted_at": datetime.now().isoformat(),
                            "source_path": str(source_path),
                            "trash_path": str(trash_path),
                        },
                        f,
                    )
            else:
                print(f"File {source_path} does not exist, skipping trash move")
        except Exception as e:
            print(f"Error processing deleted annotation data: {e}")

    # Clear the tracked objects
    session.deleted_annotation_data_info = []


class DataRepresentation(Enum):
    # Grayscale PNG (when stored as RGB/RGBA, the red channel is read)
    # 0 = background, >0 = foreground
    BINARY = "BINARY"

    # Two-channel binary mask stored in R and G:
    # R = annotation, G = uncertain/questionable region
    RG_MASK = "RG_MASK"

    # Per-pixel float mask (e.g., soft segmentation, probability map)
    # If stored as 8-bit unsigned integers (0–255) scaled to [0.0–1.0]
    FLOAT = "FLOAT"

    # Multi-label segmentation — each bit in an integer represents a label.
    # For example:
    #   0x00 => 00000000 => background
    #   0x01 => 00000001 => feature 1 present
    #   0x02 => 00000010 => feature 2 present
    #   0x04 => 00000100 => feature 3 present
    #   0x03 => 00000011 => feature 1 + feature 2 present
    MULTI_LABEL = "MULTI_LABEL"

    # Multi-class segmentation — each voxel/pixel is assigned exactly one class.
    # For example:
    #   0 = background
    #   1 = ILM
    #   2 = GCL
    #   3 = IPL
    #   ...
    MULTI_CLASS = "MULTI_CLASS"


class AnnotationTypeBase(Base):
    AnnotationTypeName: str = Field(max_length=45)
    DataRepresentation: DataRepresentation


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
