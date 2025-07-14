from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from .Annotation import SegmentationMixin
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from .base import Base

if TYPE_CHECKING:
    pass


class ModelBase(Base):
    ModelName: str = Field(max_length=45, unique=True)
    Version: str = Field(max_length=45, unique=True)
    ModelType: str = Field(max_length=45)
    Description: str | None = Field(max_length=255, default=None)


class Model(ModelBase, table=True):
    __tablename__ = "Model"
    ModelID: int | None = Field(default=None, primary_key=True)
    DateInserted: datetime = Field(default_factory=datetime.now)

    __mapper_args__ = {"polymorphic_on": "ModelType", "polymorphic_identity": "Model"}
    __table_args__ = (UniqueConstraint("ModelName", "Version"),)


class SegmentationModel(Model):
    __mapper_args__ = {
        "polymorphic_identity": "segmentation",
    }


class SegmentationOutputBase(Base, SegmentationMixin):
    """
    Used for segmentation (i.e. masks)
    """
    ImageInstanceID: int = Field(
        foreign_key="ImageInstance.ImageInstanceID", ondelete="CASCADE"
    )
    SegmentationModelID: int = Field(foreign_key="Model.ModelID")


class SegmentationOutput(SegmentationOutputBase, table=True):
    __tablename__ = "SegmentationOutput"

    SegmentationOutputID: int | None = Field(default=None, primary_key=True)
    DateInserted: datetime = Field(default_factory=datetime.now)
