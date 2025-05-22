import enum
import gzip
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, List, Optional

import numpy as np
from PIL import Image
from sqlalchemy import Column, Index, UniqueConstraint, event, select
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (AnnotationData, AnnotationType, Creator, Feature,
                            ImageInstance, Patient, Series, Study)


class Annotation(Base, table=True):
    """
    This is used for segmentation (i.e. masks)
     - made by creator
     - representing a feature

    """

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

    AnnotationID: int = Field(primary_key=True)

    # Patient is required, Study, Series and ImageInstance are optional
    # TODO: perhaps only ImageInstance is required and the others should be removed
    PatientID: int = Field(foreign_key="Patient.PatientID")
    Patient: "Patient" = Relationship(back_populates="Annotations")

    StudyID: Optional[int] = Field(default=None, foreign_key="Study.StudyID")
    Study: Optional["Study"] = Relationship(back_populates="Annotations")

    SeriesID: Optional[int] = Field(default=None, foreign_key="Series.SeriesID")
    Series: Optional["Series"] = Relationship(back_populates="Annotations")

    ImageInstanceID: Optional[int] = Field(
        default=None, foreign_key="ImageInstance.ImageInstanceID", ondelete="CASCADE"
    )
    ImageInstance: Optional["ImageInstance"] = Relationship(
        back_populates="Annotations"
    )

    CreatorID: int = Field(foreign_key="Creator.CreatorID")
    Creator: "Creator" = Relationship(back_populates="Annotations")

    FeatureID: int = Field(foreign_key="Feature.FeatureID")
    Feature: "Feature" = Relationship(back_populates="Annotations")

    AnnotationTypeID: int = Field(foreign_key="AnnotationType.AnnotationTypeID")
    AnnotationType: "AnnotationType" = Relationship(back_populates="Annotations")

    # Not used currently, but could be used to define 'masked' segmentations
    AnnotationReferenceID: Optional[int] = Field(
        default=None, foreign_key="Annotation.AnnotationID"
    )
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

    # soft delete
    Inactive: bool = False

    DateInserted: datetime = Field(default_factory=datetime.now)

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
    return np.array(Image.open(str(filepath)))


def load_binary(filepath: Path, shape) -> np.ndarray:
    ext = filepath.suffix.lower()
    if ext == ".gz":
        with gzip.open(str(filepath), "rb") as f:
            raw = np.frombuffer(f.read(), dtype=np.uint8)
    else:
        with open(str(filepath), "rb") as f:
            raw = np.frombuffer(f.read(), dtype=np.uint8)
    return raw.reshape(shape, order="C")


class AnnotationData(Base, table=True):
    """
    This is used for storing the actual data of the annotation
    """

    __tablename__ = "AnnotationData"
    __table_args__ = (Index("fk_AnnotationData_Annotation1_idx", "AnnotationID"),)

    AnnotationID: int = Field(
        foreign_key="Annotation.AnnotationID",
        ondelete="CASCADE",
        primary_key=True,
    )
    Annotation: "Annotation" = Relationship(back_populates="AnnotationData")

    ScanNr: int = Field(primary_key=True)

    DatasetIdentifier: str = Field(max_length=45, unique=True)
    MediaType: str = Field(max_length=45)

    ValueInt: int | None
    ValueFloat: float | None

    # Different sql DBs have different size specification for blobs.
    # This maps to BLOB by default (up to 1GB in sqlite) and to LONGBLOB in MySQL.
    # see: https://docs.sqlalchemy.org/en/20/core/type_basics.html#using-uppercase-and-backend-specific-types-for-multiple-backends
    ValueBlob: bytes | None = Field(
        default=None,
        sa_column=Column(LONGBLOB, nullable=True),
    )

    DateModified: Optional[datetime] = Field(
        default_factory=datetime.now, sa_column_kwargs={"onupdate": datetime.now}
    )

    @classmethod
    def create(
        cls,
        annotation: "Annotation",
        file_extension: str = "png",
        scan_nr: int = 0,
    ) -> "AnnotationData":
        annotation_data = cls()
        annotation_data.Annotation = annotation
        annotation_data.ScanNr = scan_nr
        annotation_data.DatasetIdentifier = annotation_data.default_path(file_extension)

        annotation_data.MediaType = (
            "image/png"
            if file_extension.lower() == "png"
            else "application/octet-stream"
        )
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

    def default_path(self, ext: str) -> str:
        a = self.Annotation
        return f"{a.Patient.PatientIdentifier}/{a.AnnotationID}_{self.ScanNr}.{ext}"

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
    if Base.config.trash_path is None:  # only run if trash_path is set
        return
    session.deleted_annotation_data_info = [
        {
            "path": str(obj.path),
            "trash_path": str(obj.trash_path),
            "annotation": obj.Annotation.to_dict(),
            "annotation_data": obj.to_dict(),
        }
        for obj in session.deleted
        if isinstance(obj, AnnotationData)
    ]


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


class AnnotationType(Base, table=True):
    __tablename__ = "AnnotationType"
    __table_args__ = (
        UniqueConstraint(
            "AnnotationTypeName",
            "Interpretation",
            name="AnnotationTypeNameInterpretation_UNIQUE",
        ),
    )
    AnnotationTypeID: int = Field(primary_key=True)
    AnnotationTypeName: str = Field(max_length=45)
    Interpretation: str = Field(max_length=45)

    Annotations: List["Annotation"] = Relationship(back_populates="AnnotationType")

    @classmethod
    def name_interpretation_to_id(cls, session: Session) -> dict[tuple[str, str], int]:
        return {
            (a.AnnotationTypeName, a.Interpretation): a.AnnotationTypeID
            for a in cls.fetch_all(session)
        }

class FeatureModalityEnum(enum.Enum):
    OCT = 1
    CF = 2


class Feature(Base, table=True):
    __tablename__ = "Feature"
    _name_column: ClassVar[str] = "FeatureName"
    
    FeatureID: int = Field(primary_key=True)
    FeatureName: str = Field(max_length=60, unique=True)

    Annotations: List['Annotation'] = Relationship(back_populates="Feature")
    Modality: Optional[FeatureModalityEnum]

    DateInserted: datetime = Field(default_factory=datetime.now)