from __future__ import annotations

from enum import Enum
from typing import List, Optional, Set

import pandas as pd

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    cast,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from eyened_orm.segmentation import Model, ModelKind
from eyened_orm.image_instance import ImageInstance
from eyened_orm.study import Study
from eyened_orm.patient import Patient
from eyened_orm.project import Project
from eyened_orm.series import Series

from .base import Base
from .image_instance import Laterality
from .types import OptionalEnum


class AttributeDataType(Enum):
    String = "string"
    Float = "float"
    Int = "int"
    JSON = "json"


class AttributesModel(Model):
    __tablename__ = "AttributesModel"
    _name_column = "ModelName"

    ModelID: Mapped[int] = mapped_column(
        ForeignKey("Model.ModelID", ondelete="CASCADE"), primary_key=True
    )

    # relationships
    ModelInputs: Mapped[List["ModelInput"]] = relationship(
        "eyened_orm.attributes.ModelInput",
        back_populates="Model",
        cascade="all, delete-orphan",
    )
    OutputAttributes: Mapped[Set["AttributeDefinition"]] = relationship(
        "eyened_orm.attributes.AttributeDefinition",
        secondary="AttributesModelOutput",
        back_populates="ProducingModels",
    )
    ProducedAttributeValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue", back_populates="ProducingModel"
    )

    __mapper_args__ = {"polymorphic_identity": ModelKind.Attributes}

    def export_to_csv(
        self,
        session: Session,
        output_path: str,
        attributes: List[AttributeDefinition],
        project_names: List[str],
    ):

        attribute_values = (
            session.query(
                AttributeValue.ValueFloat,
                AttributeValue.ValueInt,
                AttributeValue.ValueText,
                AttributeDefinition.AttributeName,
                ImageInstance.ImageInstanceID,
                cast(ImageInstance.Laterality, String),
                cast(ImageInstance.ETDRSField, String),
                Patient.PatientIdentifier,
                Study.StudyDate,
                Project.ProjectName,
            )
            .join(AttributeDefinition)
            .filter(AttributeDefinition.AttributeName.in_(attributes))
            .filter(AttributeDefinition.AttributeDataType != AttributeDataType.JSON)
            .join(AttributesModel)
            .filter(AttributesModel.ModelID == self.ModelID)
            .join(
                ImageInstance,
                AttributeValue.ImageInstanceID == ImageInstance.ImageInstanceID,
            )
            .join(Series, ImageInstance.SeriesID == Series.SeriesID)
            .join(Study, Series.StudyID == Study.StudyID)
            .join(Patient, Study.PatientID == Patient.PatientID)
            .join(Project, Patient.ProjectID == Project.ProjectID)
            .filter(Project.ProjectName.in_(project_names))
        )

        results = attribute_values.all()
        df = pd.DataFrame(
            results,
            columns=[
                "ValueFloat",
                "ValueInt",
                "ValueJSON",
                "AttributeName",
                "ImageInstanceID",
                "Laterality",
                "PatientIdentifier",
                "StudyDate",
                "ProjectName",
            ],
        )

        df_pivot = df.pivot(
            index=[
                "ImageInstanceID",
                "PatientIdentifier",
                "Laterality",
                "ProjectName",
                "StudyDate",
            ],
            columns="AttributeName",
            values=["ValueFloat", "ValueInt", "ValueJSON"],
        )
        df_pivot.reset_index(inplace=True)
        df_pivot.dropna(axis=1, how="all", inplace=True)
        # Remove the top-level ('ValueFloat', ...), keep only 'AttributeName' in columns
        df_pivot.columns = [
            col[1] if isinstance(col, tuple) and col[1] else col[0]
            for col in df_pivot.columns.values
        ]
        df_pivot.to_csv(output_path, index=False)


class AttributeDefinition(Base):
    __tablename__ = "AttributeDefinition"
    __table_args__ = (
        UniqueConstraint("AttributeName", name="uq_AttributeDefinition_AttributeName"),
    )

    _name_column = "AttributeName"

    AttributeID: Mapped[int] = mapped_column(primary_key=True)
    AttributeName: Mapped[str] = mapped_column(String(255))
    AttributeDataType: Mapped[AttributeDataType] = mapped_column(
        SAEnum(AttributeDataType)
    )

    # relationships
    AttributeValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue",
        back_populates="AttributeDefinition",
        lazy="noload",
    )
    ProducingModels: Mapped[Set["AttributesModel"]] = relationship(
        "eyened_orm.attributes.AttributesModel",
        secondary="AttributesModelOutput",
        back_populates="OutputAttributes",
    )


class AttributeValue(Base):
    __tablename__ = "AttributeValue"
    __table_args__ = (
        # Separate unique constraints for each entity type to handle NULLs properly
        UniqueConstraint(
            "ImageInstanceID",
            "AttributeID",
            "ModelID",
            name="uq_AttributeValue_image_attribute_model",
        ),
        UniqueConstraint(
            "SegmentationID",
            "AttributeID",
            "ModelID",
            name="uq_AttributeValue_segmentation_attribute_model",
        ),
        UniqueConstraint(
            "ModelSegmentationID",
            "AttributeID",
            "ModelID",
            name="uq_AttributeValue_modelseg_attribute_model",
        ),
        UniqueConstraint(
            "PatientID",
            "AttributeID",
            "ModelID",
            name="uq_AttributeValue_patient_attribute_model",
        ),
        UniqueConstraint(
            "StudyID",
            "AttributeID",
            "ModelID",
            name="uq_AttributeValue_study_attribute_model",
        ),
        Index("fk_AttributeValue_ImageInstance1_idx", "ImageInstanceID"),
        Index("fk_AttributeValue_Segmentation1_idx", "SegmentationID"),
        Index("fk_AttributeValue_ModelSegmentation1_idx", "ModelSegmentationID"),
        Index("fk_AttributeValue_Patient1_idx", "PatientID"),
        Index("fk_AttributeValue_Study1_idx", "StudyID"),
        Index("fk_AttributeValue_Attribute1_idx", "AttributeID"),
        Index("fk_AttributeValue_Model1_idx", "ModelID"),
        Index(
            "ix_AttributeValue_ImageInstance_Attribute",
            "ImageInstanceID",
            "AttributeID",
        ),
        Index(
            "ix_AttributeValue_Segmentation_Attribute",
            "SegmentationID",
            "AttributeID",
        ),
        Index(
            "ix_AttributeValue_ModelSegmentation_Attribute",
            "ModelSegmentationID",
            "AttributeID",
        ),
        Index(
            "ix_AttributeValue_Patient_Attribute",
            "PatientID",
            "AttributeID",
        ),
        Index("ix_AttributeValue_Study_Attribute", "StudyID", "AttributeID"),
        CheckConstraint(
            "(ImageInstanceID IS NOT NULL AND SegmentationID IS NULL AND ModelSegmentationID IS NULL AND PatientID IS NULL AND StudyID IS NULL) OR "
            "(ImageInstanceID IS NULL AND SegmentationID IS NOT NULL AND ModelSegmentationID IS NULL AND PatientID IS NULL AND StudyID IS NULL) OR "
            "(ImageInstanceID IS NULL AND SegmentationID IS NULL AND ModelSegmentationID IS NOT NULL AND PatientID IS NULL AND StudyID IS NULL) OR "
            "(ImageInstanceID IS NULL AND SegmentationID IS NULL AND ModelSegmentationID IS NULL AND PatientID IS NOT NULL AND StudyID IS NULL) OR "
            "(ImageInstanceID IS NULL AND SegmentationID IS NULL AND ModelSegmentationID IS NULL AND PatientID IS NULL AND StudyID IS NOT NULL)",
            name="ck_AttributeValue_exactly_one_entity",
        ),
    )

    AttributeValueID: Mapped[int] = mapped_column(primary_key=True)
    AttributeID: Mapped[int] = mapped_column(
        ForeignKey("AttributeDefinition.AttributeID", ondelete="CASCADE")
    )
    ModelID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Model.ModelID", ondelete="CASCADE"), nullable=True
    )

    # Entity FKs (exactly one must be non-null)
    ImageInstanceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE")
    )
    SegmentationID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Segmentation.SegmentationID", ondelete="CASCADE")
    )
    ModelSegmentationID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ModelSegmentation.ModelSegmentationID", ondelete="CASCADE")
    )
    PatientID: Mapped[Optional[int]] = mapped_column(ForeignKey("Patient.PatientID"))
    StudyID: Mapped[Optional[int]] = mapped_column(ForeignKey("Study.StudyID"))
    Laterality: Mapped[Optional[Laterality]] = mapped_column(OptionalEnum(Laterality))

    ValueFloat: Mapped[Optional[float]]
    ValueInt: Mapped[Optional[int]]
    ValueText: Mapped[Optional[str]] = mapped_column(String(255))
    ValueJSON: Mapped[Optional[dict]] = mapped_column(JSON)

    # relationships
    AttributeDefinition: Mapped["AttributeDefinition"] = relationship(
        "eyened_orm.attributes.AttributeDefinition", back_populates="AttributeValues"
    )
    ProducingModel: Mapped[Optional["Model"]] = relationship(
        "eyened_orm.segmentation.Model", back_populates="ProducedAttributeValues"
    )

    # Entity relationships
    ImageInstance: Mapped[Optional["ImageInstance"]] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="AttributeValues"
    )  # type: ignore[name-defined]
    Segmentation: Mapped[Optional["Segmentation"]] = relationship(
        "eyened_orm.segmentation.Segmentation", back_populates="AttributeValues"
    )  # type: ignore[name-defined]
    ModelSegmentation: Mapped[Optional["ModelSegmentation"]] = relationship(
        "eyened_orm.segmentation.ModelSegmentation", back_populates="AttributeValues"
    )  # type: ignore[name-defined]
    Patient: Mapped[Optional["Patient"]] = relationship(
        "eyened_orm.patient.Patient", back_populates="AttributeValues"
    )  # type: ignore[name-defined]
    Study: Mapped[Optional["Study"]] = relationship(
        "eyened_orm.study.Study", back_populates="AttributeValues"
    )  # type: ignore[name-defined]

    # Provenance tracking
    InputValues: Mapped[Set["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue",
        secondary="AttributeValueInput",
        primaryjoin="AttributeValue.AttributeValueID == AttributeValueInput.OutputAttributeValueID",
        secondaryjoin="AttributeValue.AttributeValueID == AttributeValueInput.InputAttributeValueID",
        back_populates="UsedByValues",
    )
    UsedByValues: Mapped[Set["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue",
        secondary="AttributeValueInput",
        primaryjoin="AttributeValue.AttributeValueID == AttributeValueInput.InputAttributeValueID",
        secondaryjoin="AttributeValue.AttributeValueID == AttributeValueInput.OutputAttributeValueID",
        back_populates="InputValues",
    )

    @property
    def value(self):
        attr_type = self.AttributeDefinition.AttributeDataType
        if attr_type == AttributeDataType.Float:
            return self.ValueFloat
        elif attr_type == AttributeDataType.Int:
            return self.ValueInt
        elif attr_type == AttributeDataType.String:
            return self.ValueText
        elif attr_type == AttributeDataType.JSON:
            return self.ValueJSON
        else:
            raise ValueError(f"Unsupported attribute data type: {attr_type}")


# Junction table for model output declarations
class AttributesModelOutput(Base):
    __tablename__ = "AttributesModelOutput"

    ModelID: Mapped[int] = mapped_column(
        ForeignKey("AttributesModel.ModelID", ondelete="CASCADE"), primary_key=True
    )
    AttributeID: Mapped[int] = mapped_column(
        ForeignKey("AttributeDefinition.AttributeID", ondelete="CASCADE"),
        primary_key=True,
    )


# Model input dependencies
class ModelInput(Base):
    __tablename__ = "ModelInput"
    __table_args__ = (
        UniqueConstraint(
            "ModelID", "InputAttributeID", name="uq_ModelInput_ModelID_InputAttributeID"
        ),
        Index("fk_ModelInput_Model1_idx", "ModelID"),
        Index("fk_ModelInput_Attribute1_idx", "InputAttributeID"),
    )

    ModelInputID: Mapped[int] = mapped_column(primary_key=True)
    ModelID: Mapped[int] = mapped_column(
        ForeignKey("AttributesModel.ModelID", ondelete="CASCADE")
    )
    InputAttributeID: Mapped[int] = mapped_column(
        ForeignKey("AttributeDefinition.AttributeID", ondelete="CASCADE")
    )
    InputName: Mapped[str] = mapped_column(String(255))

    # relationships
    Model: Mapped["AttributesModel"] = relationship(
        "eyened_orm.attributes.AttributesModel", back_populates="ModelInputs"
    )
    InputAttribute: Mapped["AttributeDefinition"] = relationship(
        "eyened_orm.attributes.AttributeDefinition"
    )


# Provenance tracking
class AttributeValueInput(Base):
    __tablename__ = "AttributeValueInput"

    OutputAttributeValueID: Mapped[int] = mapped_column(
        ForeignKey("AttributeValue.AttributeValueID", ondelete="CASCADE"),
        primary_key=True,
    )
    InputAttributeValueID: Mapped[int] = mapped_column(
        ForeignKey("AttributeValue.AttributeValueID", ondelete="CASCADE"),
        primary_key=True,
    )

    # relationships
    OutputValue: Mapped["AttributeValue"] = relationship(
        "eyened_orm.attributes.AttributeValue",
        foreign_keys=[OutputAttributeValueID],
        overlaps="InputValues,UsedByValues",
    )
    InputValue: Mapped["AttributeValue"] = relationship(
        "eyened_orm.attributes.AttributeValue",
        foreign_keys=[InputAttributeValueID],
        overlaps="InputValues,UsedByValues",
    )
