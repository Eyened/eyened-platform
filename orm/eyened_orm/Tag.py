from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Column, ForeignKey, String, Table, func, select, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, Session, relationship

from eyened_orm.base import Base, ForeignKeyIndex, CompositeUniqueConstraint

if TYPE_CHECKING:
    from eyened_orm import Study, ImageInstance, Annotation, Segmentation, FormAnnotation

class TagType(enum.Enum):
    Study = 1
    ImageInstance = 2
    Annotation = 3
    Segmentation = 4
    FormAnnotation = 5


class Tag(Base):
    __tablename__ = "Tag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(primary_key=True)
    TagName: Mapped[str] = mapped_column(String(256), unique=True)
    TagType: Mapped[TagType] = mapped_column(SAEnum(TagType))

    TagDescription: Mapped[str] = mapped_column(String(256))

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    StudyTagLinks: Mapped[List["StudyTagLink"]] = relationship(back_populates="Tag")
    ImageInstanceTagLinks: Mapped[List["ImageInstanceTagLink"]] = relationship(back_populates="Tag")
    AnnotationTagLinks: Mapped[List["AnnotationTagLink"]] = relationship(back_populates="Tag")
    SegmentationTagLinks: Mapped[List["SegmentationTagLink"]] = relationship(back_populates="Tag")
    FormAnnotationTagLinks: Mapped[List["FormAnnotationTagLink"]] = relationship(back_populates="Tag")

    
class CreatorTagLink(Base):
    __tablename__ = "CreatorTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
    )
    CreatorID: Mapped[int] = mapped_column(primary_key=True)
    TagID: Mapped[int] = mapped_column(primary_key=True)
    
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())


class StudyTagLink(Base):
    __tablename__ = "StudyTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Study", "StudyID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID"), primary_key=True)
    StudyID: Mapped[int] = mapped_column(ForeignKey("Study.StudyID"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(back_populates="StudyTagLinks")
    Study: Mapped["Study"] = relationship(back_populates="StudyTagLinks")

class ImageInstanceTagLink(Base):
    __tablename__ = "ImageInstanceTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "ImageInstance", "ImageInstanceID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID"), primary_key=True)
    ImageInstanceID: Mapped[int] = mapped_column(ForeignKey("ImageInstance.ImageInstanceID"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(back_populates="ImageInstanceTagLinks")
    ImageInstance: Mapped["ImageInstance"] = relationship(back_populates="ImageInstanceTagLinks")

class AnnotationTagLink(Base):
    __tablename__ = "AnnotationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Annotation", "AnnotationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID"), primary_key=True)
    AnnotationID: Mapped[int] = mapped_column(ForeignKey("Annotation.AnnotationID"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(back_populates="AnnotationTagLinks")


class SegmentationTagLink(Base):
    __tablename__ = "SegmentationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Segmentation", "SegmentationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID"), primary_key=True)
    SegmentationID: Mapped[int] = mapped_column(ForeignKey("Segmentation.SegmentationID"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(back_populates="SegmentationTagLinks")
    Segmentation: Mapped["Segmentation"] = relationship(back_populates="SegmentationTagLinks")


class FormAnnotationTagLink(Base):
    __tablename__ = "FormAnnotationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "FormAnnotation", "FormAnnotationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID"), primary_key=True)
    FormAnnotationID: Mapped[int] = mapped_column(ForeignKey("FormAnnotation.FormAnnotationID"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(back_populates="FormAnnotationTagLinks")
    FormAnnotation: Mapped["FormAnnotation"] = relationship(back_populates="FormAnnotationTagLinks")