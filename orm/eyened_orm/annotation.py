import gzip
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, List, Optional

import numpy as np
from PIL import Image
from sqlalchemy import ForeignKey, Index, UniqueConstraint, String, func
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (
        Creator,
        Feature,
        ImageInstance,
        Patient,
        Series,
        Study,
    )


class Annotation(Base):
    """Annotation metadata and references; actual data lives in AnnotationData."""

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

    AnnotationID: Mapped[int] = mapped_column(primary_key=True)

    # Patient is required, Study, Series and ImageInstance are optional
    PatientID: Mapped[int] = mapped_column(ForeignKey("Patient.PatientID"))
    StudyID: Mapped[Optional[int]] = mapped_column(ForeignKey("Study.StudyID"))
    SeriesID: Mapped[Optional[int]] = mapped_column(ForeignKey("Series.SeriesID"))
    ImageInstanceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE")
    )
    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    FeatureID: Mapped[int] = mapped_column(ForeignKey("Feature.FeatureID"))
    AnnotationTypeID: Mapped[int] = mapped_column(
        ForeignKey("AnnotationType.AnnotationTypeID")
    )
    AnnotationReferenceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Annotation.AnnotationID", ondelete="CASCADE")
    )
    Inactive: Mapped[bool] = mapped_column(default=False)

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Patient: Mapped[Optional["Patient"]] = relationship("eyened_orm.patient.Patient", back_populates="Annotations")
    Study: Mapped[Optional["Study"]] = relationship("eyened_orm.study.Study", back_populates="Annotations")
    Series: Mapped[Optional["Series"]] = relationship("eyened_orm.series.Series", back_populates="Annotations")
    ImageInstance: Mapped[Optional["ImageInstance"]] = relationship(
        "eyened_orm.image_instance.ImageInstance",
        back_populates="Annotations"
    )
    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", back_populates="Annotations")

    AnnotationType: Mapped["AnnotationType"] = relationship("eyened_orm.annotation.AnnotationType", back_populates="Annotations")
    AnnotationReference: Mapped[Optional["Annotation"]] = relationship(
        "eyened_orm.annotation.Annotation",
        back_populates="ChildAnnotations", remote_side="Annotation.AnnotationID"
    )

    ChildAnnotations: Mapped[List["Annotation"]] = relationship(
        "eyened_orm.annotation.Annotation",
        back_populates="AnnotationReference",
        passive_deletes=True,
    )
    # Actual data is stored in AnnotationData
    AnnotationData: Mapped[List["AnnotationData"]] = relationship(
        "eyened_orm.annotation.AnnotationData",
        back_populates="Annotation", passive_deletes=True
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


class AnnotationData(Base):
    """Stores the actual data of the annotation (e.g., segmentation)."""

    __tablename__ = "AnnotationData"

    __table_args__ = (Index("fk_AnnotationData_Annotation1_idx", "AnnotationID"),)

    AnnotationID: Mapped[int] = mapped_column(
        ForeignKey("Annotation.AnnotationID", ondelete="CASCADE"), primary_key=True
    )
    # use -1 for all scans (e.g. enface OCT)
    ScanNr: Mapped[int] = mapped_column(primary_key=True)

    ValueInt: Mapped[Optional[int]]
    ValueFloat: Mapped[Optional[float]]
    ValueBlob: Mapped[Optional[bytes]] = mapped_column(LONGBLOB)

    DatasetIdentifier: Mapped[str] = mapped_column(String(45), unique=True)
    DateModified: Mapped[Optional[datetime]] = mapped_column(onupdate=func.now())
    MediaType: Mapped[str] = mapped_column(String(45))

    Annotation: Mapped["Annotation"] = relationship("eyened_orm.annotation.Annotation", back_populates="AnnotationData")

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
        return self.config.annotations_path / self.DatasetIdentifier

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


class AnnotationType(Base):
    __tablename__ = "AnnotationType"

    __table_args__ = (
        UniqueConstraint(
            "AnnotationTypeName",
            "Interpretation",
            name="AnnotationTypeNameInterpretation_UNIQUE",
        ),
    )

    _name_column: ClassVar[str] = "AnnotationTypeName"

    AnnotationTypeID: Mapped[int] = mapped_column(primary_key=True)
    AnnotationTypeName: Mapped[str] = mapped_column(String(45))
    Interpretation: Mapped[str] = mapped_column(String(45))

    Annotations: Mapped[List["Annotation"]] = relationship("eyened_orm.annotation.Annotation", back_populates="AnnotationType")
