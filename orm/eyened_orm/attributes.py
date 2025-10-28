from __future__ import annotations

from enum import Enum
from typing import List, Optional

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint, Enum as SAEnum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyened_orm.segmentation import Model

from .base import Base


class AttributeDataType(Enum):
    String = "string"
    Float = "float"
    Int = "int"
    JSON = "json"


class AttributesModel(Model):
    __tablename__ = "AttributesModel"

    ModelID: Mapped[int] = mapped_column(ForeignKey("Model.ModelID", ondelete="CASCADE"), primary_key=True)

    # relationships
    ModelInputs: Mapped[List["ModelInput"]] = relationship("eyened_orm.attributes.ModelInput", back_populates="Model", cascade="all, delete-orphan")
    OutputAttributes: Mapped[List["AttributeDefinition"]] = relationship("eyened_orm.attributes.AttributeDefinition", secondary="AttributesModelOutput", back_populates="ProducingModels")
    ProducedAttributeValues: Mapped[List["AttributeValue"]] = relationship("eyened_orm.attributes.AttributeValue", back_populates="ProducingModel")

    __mapper_args__ = {"polymorphic_identity": "attributes"}


class AttributeDefinition(Base):
    __tablename__ = "AttributeDefinition"
    __table_args__ = (UniqueConstraint("AttributeName", name="uq_AttributeDefinition_AttributeName"),)

    AttributeID: Mapped[int] = mapped_column(primary_key=True)
    AttributeName: Mapped[str] = mapped_column(String(255))
    AttributeDataType: Mapped[AttributeDataType] = mapped_column(SAEnum(AttributeDataType))

    # relationships
    AttributeValues: Mapped[List["AttributeValue"]] = relationship("eyened_orm.attributes.AttributeValue", back_populates="AttributeDefinition", lazy="selectin")
    ProducingModels: Mapped[List["AttributesModel"]] = relationship("eyened_orm.attributes.AttributesModel", secondary="AttributesModelOutput", back_populates="OutputAttributes")


class AttributeValue(Base):
    __tablename__ = "AttributeValue"
    __table_args__ = (
        # Separate unique constraints for each entity type to handle NULLs properly
        UniqueConstraint("ImageInstanceID", "AttributeID", "ModelID", name="uq_AttributeValue_image_attribute_model"),
        UniqueConstraint("SegmentationID", "AttributeID", "ModelID", name="uq_AttributeValue_segmentation_attribute_model"),
        UniqueConstraint("ModelSegmentationID", "AttributeID", "ModelID", name="uq_AttributeValue_modelseg_attribute_model"),
        Index("fk_AttributeValue_ImageInstance1_idx", "ImageInstanceID"),
        Index("fk_AttributeValue_Segmentation1_idx", "SegmentationID"),
        Index("fk_AttributeValue_ModelSegmentation1_idx", "ModelSegmentationID"),
        Index("fk_AttributeValue_Attribute1_idx", "AttributeID"),
        Index("fk_AttributeValue_Model1_idx", "ModelID"),
        CheckConstraint(
            "(ImageInstanceID IS NOT NULL AND SegmentationID IS NULL AND ModelSegmentationID IS NULL) OR (ImageInstanceID IS NULL AND SegmentationID IS NOT NULL AND ModelSegmentationID IS NULL) OR (ImageInstanceID IS NULL AND SegmentationID IS NULL AND ModelSegmentationID IS NOT NULL)",
            name="ck_AttributeValue_exactly_one_entity",
        ),
    )

    AttributeValueID: Mapped[int] = mapped_column(primary_key=True)
    AttributeID: Mapped[int] = mapped_column(ForeignKey("AttributeDefinition.AttributeID", ondelete="CASCADE"))
    ModelID: Mapped[int] = mapped_column(ForeignKey("Model.ModelID", ondelete="CASCADE"))

    # Entity FKs (exactly one must be non-null)
    ImageInstanceID: Mapped[Optional[int]] = mapped_column(ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE"))
    SegmentationID: Mapped[Optional[int]] = mapped_column(ForeignKey("Segmentation.SegmentationID", ondelete="CASCADE"))
    ModelSegmentationID: Mapped[Optional[int]] = mapped_column(ForeignKey("ModelSegmentation.ModelSegmentationID", ondelete="CASCADE"))

    ValueFloat: Mapped[Optional[float]]
    ValueInt: Mapped[Optional[int]]
    ValueText: Mapped[Optional[str]] = mapped_column(String(255))
    ValueJSON: Mapped[Optional[dict]] = mapped_column(JSON)

    # relationships
    AttributeDefinition: Mapped["AttributeDefinition"] = relationship("eyened_orm.attributes.AttributeDefinition", back_populates="AttributeValues")
    ProducingModel: Mapped["Model"] = relationship("eyened_orm.segmentation.Model", back_populates="ProducedAttributeValues")

    # Entity relationships
    ImageInstance: Mapped[Optional["ImageInstance"]] = relationship("eyened_orm.image_instance.ImageInstance", back_populates="AttributeValues")  # type: ignore[name-defined]
    Segmentation: Mapped[Optional["Segmentation"]] = relationship("eyened_orm.segmentation.Segmentation", back_populates="AttributeValues")  # type: ignore[name-defined]
    ModelSegmentation: Mapped[Optional["ModelSegmentation"]] = relationship("eyened_orm.segmentation.ModelSegmentation", back_populates="AttributeValues")  # type: ignore[name-defined]

    # Provenance tracking
    InputValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue", secondary="AttributeValueInput", primaryjoin="AttributeValue.AttributeValueID == AttributeValueInput.OutputAttributeValueID", secondaryjoin="AttributeValue.AttributeValueID == AttributeValueInput.InputAttributeValueID", back_populates="UsedByValues"
    )
    UsedByValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue", secondary="AttributeValueInput", primaryjoin="AttributeValue.AttributeValueID == AttributeValueInput.InputAttributeValueID", secondaryjoin="AttributeValue.AttributeValueID == AttributeValueInput.OutputAttributeValueID", back_populates="InputValues"
    )


# Junction table for model output declarations
class AttributesModelOutput(Base):
    __tablename__ = "AttributesModelOutput"

    ModelID: Mapped[int] = mapped_column(ForeignKey("AttributesModel.ModelID", ondelete="CASCADE"), primary_key=True)
    AttributeID: Mapped[int] = mapped_column(ForeignKey("AttributeDefinition.AttributeID", ondelete="CASCADE"), primary_key=True)


# Model input dependencies
class ModelInput(Base):
    __tablename__ = "ModelInput"
    __table_args__ = (
        UniqueConstraint("ModelID", "InputAttributeID", name="uq_ModelInput_ModelID_InputAttributeID"),
        Index("fk_ModelInput_Model1_idx", "ModelID"),
        Index("fk_ModelInput_Attribute1_idx", "InputAttributeID"),
    )

    ModelInputID: Mapped[int] = mapped_column(primary_key=True)
    ModelID: Mapped[int] = mapped_column(ForeignKey("AttributesModel.ModelID", ondelete="CASCADE"))
    InputAttributeID: Mapped[int] = mapped_column(ForeignKey("AttributeDefinition.AttributeID", ondelete="CASCADE"))
    InputName: Mapped[str] = mapped_column(String(255))

    # relationships
    Model: Mapped["AttributesModel"] = relationship("eyened_orm.attributes.AttributesModel", back_populates="ModelInputs")
    InputAttribute: Mapped["AttributeDefinition"] = relationship("eyened_orm.attributes.AttributeDefinition")


# Provenance tracking
class AttributeValueInput(Base):
    __tablename__ = "AttributeValueInput"

    OutputAttributeValueID: Mapped[int] = mapped_column(ForeignKey("AttributeValue.AttributeValueID", ondelete="CASCADE"), primary_key=True)
    InputAttributeValueID: Mapped[int] = mapped_column(ForeignKey("AttributeValue.AttributeValueID", ondelete="CASCADE"), primary_key=True)

    # relationships
    OutputValue: Mapped["AttributeValue"] = relationship("eyened_orm.attributes.AttributeValue", foreign_keys=[OutputAttributeValueID], overlaps="InputValues,UsedByValues")
    InputValue: Mapped["AttributeValue"] = relationship("eyened_orm.attributes.AttributeValue", foreign_keys=[InputAttributeValueID], overlaps="InputValues,UsedByValues")
