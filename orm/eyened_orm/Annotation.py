import gzip
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, List, Optional

import numpy as np
from PIL import Image
from sqlalchemy import Column, Index, UniqueConstraint
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

    Patient: Optional["Patient"] = Relationship(back_populates="Annotations")
    Study: Optional["Study"] = Relationship(back_populates="Annotations")
    Series: Optional["Series"] = Relationship(back_populates="Annotations")
    ImageInstance: Optional["ImageInstance"] = Relationship(
        back_populates="Annotations"
    )
    Creator: "Creator" = Relationship(back_populates="Annotations")

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

    ValueInt: int | None
    ValueFloat: float | None
    ValueBlob: bytes | None = Field(sa_column=Column(LONGBLOB))


class AnnotationData(AnnotationDataBase, table=True):
    __tablename__ = "AnnotationData"

    __table_args__ = (Index("fk_AnnotationData_Annotation1_idx", "AnnotationID"),)
    Annotation: "Annotation" = Relationship(back_populates="AnnotationData")

    DatasetIdentifier: str = Field(max_length=45, unique=True)
    DateModified: datetime | None = Field(
        default_factory=datetime.now, sa_column_kwargs={"onupdate": datetime.now}
    )
    MediaType: str = Field(max_length=45)

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
        interpretation = self.Annotation.AnnotationType.Interpretation

        if interpretation == "R/G mask":
            assert len(data.shape) == 3, "Expected color image"
            if mask_type == "segmentation":
                return data[:, :, 0] > 0  # red channel
            elif mask_type == "questionable":
                return data[:, :, 1] > 0  # green channel
            else:
                raise ValueError(f"Unsupported mask type: {mask_type}")

        elif interpretation == "Binary mask":
            assert len(data.shape) == 2, "Expected grayscale image"
            return data > 0
        else:
            raise ValueError(f"Unsupported annotation type {interpretation}")

    @property
    def segmentation_mask(self) -> np.ndarray:
        return self.get_mask("segmentation")

    @property
    def questionable_mask(self) -> np.ndarray:
        return self.get_mask("questionable")


class AnnotationTypeBase(Base):
    AnnotationTypeName: str = Field(max_length=45)
    Interpretation: str = Field(max_length=45)


class AnnotationType(AnnotationTypeBase, table=True):
    __tablename__ = "AnnotationType"

    __table_args__ = (
        UniqueConstraint(
            "AnnotationTypeName",
            "Interpretation",
            name="AnnotationTypeNameInterpretation_UNIQUE",
        ),
    )

    _name_column: ClassVar[str] = "AnnotationTypeName"

    AnnotationTypeID: int = Field(primary_key=True)

    Annotations: List["Annotation"] = Relationship(back_populates="AnnotationType")
