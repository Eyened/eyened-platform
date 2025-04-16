from __future__ import annotations

import enum
import gzip
import json
import os
import shutil
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional

import numpy as np
from PIL import Image
from sqlalchemy import (ForeignKey, LargeBinary, String, UniqueConstraint,
                        event, func, select)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, ForeignKeyIndex

if TYPE_CHECKING:
    from eyened_orm import (AnnotationType, Creator, Feature, ImageInstance,
                            Patient, Series, Study)


class Annotation(Base):
    """
    This is used for segmentation (i.e. masks) 
     - made by creator 
     - representing a feature

    """
    __tablename__ = "Annotation"

    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        ForeignKeyIndex(__tablename__, "Feature", "FeatureID"),
        ForeignKeyIndex(__tablename__, "Study", "StudyID"),
        ForeignKeyIndex(__tablename__, "ImageInstance", "ImageInstanceID"),
        ForeignKeyIndex(__tablename__, "AnnotationType", "AnnotationTypeID"),
        ForeignKeyIndex(__tablename__, "Patient", "PatientID"),
        ForeignKeyIndex(__tablename__, "Series", "SeriesID"),
    )

    AnnotationID: Mapped[int] = mapped_column("AnnotationID", primary_key=True)

    # Patient is required, Study, Series and ImageInstance are optional
    # TODO: perhaps only ImageInstance is required and the others should be removed
    PatientID: Mapped[int] = mapped_column(ForeignKey("Patient.PatientID"))
    Patient: Mapped[Patient] = relationship(back_populates="Annotations")

    StudyID: Mapped[Optional[int]] = mapped_column(ForeignKey("Study.StudyID"))
    Study: Mapped[Optional[Study]] = relationship(back_populates="Annotations")

    SeriesID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Series.SeriesID"))
    Series: Mapped[Optional[Series]] = relationship(
        back_populates="Annotations")

    ImageInstanceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE")
    )
    ImageInstance: Mapped[Optional[ImageInstance]] = relationship(
        back_populates="Annotations"
    )

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    Creator: Mapped[Creator] = relationship(back_populates="Annotations")

    FeatureID: Mapped[int] = mapped_column(ForeignKey("Feature.FeatureID"))
    Feature: Mapped[Feature] = relationship(back_populates="Annotations")

    AnnotationTypeID: Mapped[int] = mapped_column(
        ForeignKey("AnnotationType.AnnotationTypeID")
    )
    AnnotationType: Mapped[AnnotationType] = relationship(
        back_populates="Annotations")

    # Not used currently, but could be used to define 'masked' segmentations
    AnnotationReferenceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Annotation.AnnotationID")
    )
    AnnotationReference: Mapped[Optional[Annotation]] = relationship(
        "Annotation", back_populates="ChildAnnotations", remote_side="Annotation.AnnotationID"
    )
    ChildAnnotations: Mapped[List[Annotation]] = relationship(
        "Annotation", back_populates="AnnotationReference", cascade="all, delete-orphan"
    )

    # Actual data is stored in AnnotationData
    AnnotationData: Mapped[List[AnnotationData]] = relationship(
        back_populates="Annotation", cascade="all,delete-orphan"
    )

    # soft delete
    Inactive: Mapped[bool] = mapped_column(default=False)

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

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

    def __repr__(self):
        return f"Annotation({self.AnnotationID}, {self.FeatureName}, {self.Creator.CreatorName})"

    @classmethod
    def create(
        cls,
        instance: ImageInstance,
        feature: Feature,
        creator: Creator,
        annotationType: AnnotationType,
    ) -> Annotation:
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

def load_png(filepath) -> np.ndarray:
    return np.array(Image.open(filepath))


def load_binary(filepath, shape) -> np.ndarray:
    _, ext = os.path.splitext(filepath)
    if ext.lower() in ['.gz']:
        with gzip.open(filepath, 'rb') as f:
            raw = np.frombuffer(f.read(), dtype=np.uint8)
    else:
        with open(filepath, 'rb') as f:
            raw = np.frombuffer(f.read(), dtype=np.uint8)
    return raw.reshape(shape, order='C')

class AnnotationData(Base):
    """
    This is used for storing the actual data of the annotation
    """

    __tablename__ = "AnnotationData"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Annotation", "AnnotationID"),
    )

    AnnotationID: Mapped[int] = mapped_column(
        ForeignKey("Annotation.AnnotationID", ondelete="CASCADE"), primary_key=True
    )
    Annotation: Mapped[Annotation] = relationship(
        back_populates="AnnotationData")

    ScanNr: Mapped[int] = mapped_column(primary_key=True)
    DatasetIdentifier: Mapped[str] = mapped_column(String(45), unique=True)
    MediaType: Mapped[str] = mapped_column(String(45))

    ValueInt: Mapped[Optional[int]] = mapped_column()
    ValueFloat: Mapped[Optional[float]] = mapped_column()

    # Different sql DBs have different size specification for blobs.
    # This maps to BLOB by default (up to 1GB in sqlite) and to LONGBLOB in MySQL.
    # see: https://docs.sqlalchemy.org/en/20/core/type_basics.html#using-uppercase-and-backend-specific-types-for-multiple-backends
    ValueBlob: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary().with_variant(LONGBLOB, "mysql")
    )

    DateModified: Mapped[Optional[datetime]] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    @classmethod
    def create(
        cls,
        annotation: Annotation,
        file_extension: str = "png",
        scan_nr: int = 0,
    ) -> AnnotationData:
        annotation_data = cls()
        annotation_data.Annotation = annotation
        annotation_data.ScanNr = scan_nr
        annotation_data.DatasetIdentifier = annotation_data.default_path(file_extension)
            
        annotation_data.MediaType = "image/png" if file_extension.lower() == "png" else "application/octet-stream"
        return annotation_data

    def default_path(self, ext: str) -> str:
        a = self.Annotation
        return f"{a.Patient.PatientIdentifier}/{a.AnnotationID}_{self.ScanNr}.{ext}"

    @property
    def path(self) -> str:
        if not self.config:
            raise ValueError("Configuration not initialized")
        return f"{self.config['annotations_path']}/{self.DatasetIdentifier}"

    @property
    def trash_path(self) -> str:
        if not self.config:
            raise ValueError("Configuration not initialized")
        return f"{self.config['trash_path']}/{self.DatasetIdentifier}"

    def __repr__(self):
        return f"AnnotationData({self.AnnotationID}, {self.ScanNr}, {self.DatasetIdentifier}, {self.MediaType})"

    @classmethod
    def get_columns(cls):
        return cls.__table__.columns
    
    def load_data(self) -> Any:
        """Load the annotation data from the file."""       
        if self.MediaType == 'image/png':
            return load_png(self.path)
        elif self.MediaType == 'application/octet-stream':
            instance = self.Annotation.ImageInstance
            return load_binary(self.path, (instance.Rows_y, instance.Columns_x))
        else:
            raise ValueError(f'Unsupported media type {self.media_type}')


    @property
    def mask(self, mask_type: str = "segmentation") -> np.ndarray:
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
        if self.Annotation.AnnotationType.Interpretation == 'R/G mask':
            assert len(data.shape) == 3, "Expected color image"
            data2D = data[:, :, 0]
        elif self.Annotation.AnnotationType.Interpretation == 'Binary mask':
            assert len(data.shape) == 2, "Expected grayscale image"
            data2D = data
        else:
            raise ValueError(f"Unsupported annotation type {self.Annotation.AnnotationType.Interpretation}")

        if mask_type == "segmentation":
            return data2D > 0
        elif mask_type == "questionable":
            return data2D > 0  # Placeholder for different logic if needed
        else:
            raise ValueError(f"Unsupported mask type: {mask_type}")

    @property
    def segmentation_mask(self):
        data = self.load_data()
        if self.Annotation.AnnotationType.Interpretation == 'R/G mask':
            assert len(data.shape) == 3, "Expected color image"
            data2D = data[:, :, 0] 
        elif self.Annotation.AnnotationType.Interpretation == 'Binary mask':
            assert len(data.shape) == 2, "Expected grayscale image"
            data2D = data
        else:
            raise ValueError(f"Unsupported annotation type {self.Annotation.AnnotationType.Interpretation}") 
        return data2D > 0

    @property
    def questionable_mask(self, data):
        data = self.load_data()
        if self.Annotation.AnnotationType.Interpretation == 'R/G mask':
            assert len(data.shape) == 3, "Expected color image"
            data2D = data[:, :, 0] 
        elif self.Annotation.AnnotationType.Interpretation == 'Binary mask':
            assert len(data.shape) == 2, "Expected grayscale image"
            data2D = data
        else:
            raise ValueError(f"Unsupported annotation type {self.Annotation.AnnotationType.Interpretation}") 
        return data2D > 0
    


def move_file_to_trash(annotation_data: AnnotationData) -> None:
    """Moves a file to trash folder and stores metadata alongside it."""
    source_path = annotation_data.path
    if not os.path.exists(source_path):
        print(f"File {source_path} does not exist, skipping trash move")
        return

    trash_path = annotation_data.trash_path

    try:
        shutil.move(source_path, trash_path)
        print(f"File moved to trash: {trash_path}")

        with open(f"{trash_path}.metadata.json", 'w') as f:
            json.dump({
                "annotation": annotation_data.Annotation.to_dict(),
                "annotation_data": annotation_data.to_dict(),
                "deleted_at": datetime.now().isoformat()
            }, f)

    except Exception as e:
        print(f"Error moving file {source_path} to trash: {e}")


# Track deleted AnnotationData objects
@event.listens_for(Session, "before_flush")
def receive_before_flush(session, flush_context, instances):
    """Track AnnotationData objects being deleted before they're removed from the session."""
    session.deleted_annotation_data_info = [
        {
            'path': obj.path,
            'trash_path': obj.trash_path,
            'annotation': obj.Annotation.to_dict(),
            'annotation_data': obj.to_dict()
        } 
        for obj in session.deleted if isinstance(obj, AnnotationData)
    ]


@event.listens_for(Session, "after_commit")
def receive_after_commit(session):
    """Process tracked deleted annotation data after the transaction is committed."""
    if not hasattr(session, 'deleted_annotation_data_info'):
        return
    for info in session.deleted_annotation_data_info:
        try:
            source_path = info['path']
            trash_path = info['trash_path']

            if os.path.exists(source_path):
                # Create trash directory if it doesn't exist
                os.makedirs(os.path.dirname(trash_path), exist_ok=True)

                # Move the file to trash
                shutil.move(source_path, trash_path)
                print(f"File moved to trash: {trash_path}")

                # Store metadata
                with open(f"{trash_path}.metadata.json", 'w') as f:
                    json.dump({
                        "annotation": info['annotation'],
                        "annotation_data": info['annotation_data'],
                        "deleted_at": datetime.now().isoformat()
                    }, f)
            else:
                print(
                    f"File {source_path} does not exist, skipping trash move")
        except Exception as e:
            print(f"Error processing deleted annotation data: {e}")

    # Clear the tracked objects
    session.deleted_annotation_data_info = []


class AnnotationType(Base):
    __tablename__ = "AnnotationType"

    __table_args__ = (
        UniqueConstraint(
            "AnnotationTypeName",
            "Interpretation",
            name="AnnotationTypeNameInterpretation_UNIQUE",
        ),
    )
    AnnotationTypeID: Mapped[int] = mapped_column(primary_key=True)
    AnnotationTypeName: Mapped[str] = mapped_column(String(45))
    Interpretation: Mapped[str] = mapped_column(String(45))

    Annotations: Mapped[List[Annotation]] = relationship(
        back_populates="AnnotationType"
    )

    @classmethod
    def name_interpretation_to_id(cls, session: Session):
        return {
            (a.AnnotationTypeName, a.Interpretation): a.AnnotationTypeID
            for a in cls.fetch_all(session)
        }

    def __repr__(self) -> str:
        return f"AnnotationType({self.AnnotationTypeID}, {self.AnnotationTypeName}, {self.Interpretation})"


class FeatureModalityEnum(enum.Enum):
    OCT = 1
    CF = 2


class Feature(Base):
    __tablename__ = "Feature"
    FeatureID: Mapped[int] = mapped_column(primary_key=True)
    FeatureName: Mapped[str] = mapped_column(String(60), unique=True)

    Annotations: Mapped[List[Annotation]] = relationship(
        back_populates="Feature")
    Modality: Mapped[Optional[FeatureModalityEnum]]

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional[Feature]:
        """Find a feature by name (FeatureName)."""
        return session.scalar(select(cls).where(cls.FeatureName == name))

    @classmethod
    def name_to_id(cls, session: Session) -> dict[str, int]:
        return {
            feature.FeatureName: feature.FeatureID
            for feature in cls.fetch_all(session)
        }

    def __repr__(self) -> str:
        return f"Feature({self.FeatureID}, {self.FeatureName})"
