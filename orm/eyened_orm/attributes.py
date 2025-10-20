from __future__ import annotations

from enum import Enum
from typing import List, Optional

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint, Enum as SAEnum
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
    Attributes: Mapped[List["Attribute"]] = relationship("eyened_orm.attributes.Attribute", back_populates="Model")  # type: ignore[name-defined]

    __mapper_args__ = {"polymorphic_identity": "attributes"}


class Attribute(Base):
    __tablename__ = "Attributes"
    __table_args__ = (
        UniqueConstraint("ModelID", "AttributeName", name="uq_Attributes_ModelID_AttributeName"),
        Index("fk_Attributes_Model1_idx", "ModelID"),
    )

    AttributeID: Mapped[int] = mapped_column(primary_key=True)
    AttributeName: Mapped[str] = mapped_column(String(255))
    AttributeDataType: Mapped[AttributeDataType] = mapped_column(SAEnum(AttributeDataType))
    ModelID: Mapped[int] = mapped_column(ForeignKey("Model.ModelID", ondelete="CASCADE"))

    # relationships
    Model: Mapped["AttributesModel"] = relationship("eyened_orm.attributes.AttributesModel", back_populates="Attributes")  # type: ignore[name-defined]
    ImageAttributes: Mapped[List["ImageAttribute"]] = relationship("eyened_orm.attributes.ImageAttribute", back_populates="Attribute", lazy="selectin")


class ImageAttribute(Base):
    __tablename__ = "ImageAttributes"
    __table_args__ = (
        UniqueConstraint("ImageInstanceID", "AttributeID", name="uq_ImageAttributes_ImageInstanceID_AttributeID"),
        Index("fk_ImageAttributes_ImageInstance1_idx", "ImageInstanceID"),
        Index("fk_ImageAttributes_Attribute1_idx", "AttributeID"),
    )

    ImageAttributeID: Mapped[int] = mapped_column(primary_key=True)
    ImageInstanceID: Mapped[int] = mapped_column(ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE"))
    AttributeID: Mapped[int] = mapped_column(ForeignKey("Attributes.AttributeID", ondelete="CASCADE"))

    ValueFloat: Mapped[Optional[float]]
    ValueInt: Mapped[Optional[int]]
    ValueText: Mapped[Optional[str]] = mapped_column(String(255))
    ValueJSON: Mapped[Optional[dict]] = mapped_column(JSON)

    # relationships
    ImageInstance: Mapped["ImageInstance"] = relationship("eyened_orm.image_instance.ImageInstance", back_populates="ImageAttributes")  # type: ignore[name-defined]
    Attribute: Mapped["Attribute"] = relationship("eyened_orm.attributes.Attribute", back_populates="ImageAttributes")


