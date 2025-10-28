from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Column, ForeignKey, String, Table, func, select, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, Session, relationship

from eyened_orm.base import Base, ForeignKeyIndex, CompositeUniqueConstraint

if TYPE_CHECKING:
    from eyened_orm import Study, ImageInstance, Annotation, Segmentation, FormAnnotation, Creator

class TagType(enum.Enum):
    Study = "Study"
    ImageInstance = "ImageInstance"
    Annotation = "Annotation"
    Segmentation = "Segmentation"
    FormAnnotation = "FormAnnotation"


class CreatorTagLink(Base):
    __tablename__ = "CreatorTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID", ondelete="CASCADE"), primary_key=True)
    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID", ondelete="CASCADE"), primary_key=True)
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship("eyened_orm.tag.Tag", back_populates="CreatorTagLinks")
    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", back_populates="StarredTags")


class Tag(Base):
    __tablename__ = "Tag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        CompositeUniqueConstraint(__tablename__, "TagName", "TagType"),
    )
    TagID: Mapped[int] = mapped_column(primary_key=True)
    TagName: Mapped[str] = mapped_column(String(256))
    TagType: Mapped[TagType] = mapped_column(SAEnum(TagType))

    TagDescription: Mapped[str] = mapped_column(String(256))

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    CreatorTagLinks: Mapped[List["CreatorTagLink"]] = relationship(
        "eyened_orm.tag.CreatorTagLink",
        back_populates="Tag",
        passive_deletes=True,
        lazy="selectin"
    )

    StudyTagLinks: Mapped[List["StudyTagLink"]] = relationship(
        "eyened_orm.tag.StudyTagLink",
        back_populates="Tag", 
        passive_deletes=True, 
        lazy="selectin"
    )
    ImageInstanceTagLinks: Mapped[List["ImageInstanceTagLink"]] = relationship(
        "eyened_orm.tag.ImageInstanceTagLink",
        back_populates="Tag", 
        passive_deletes=True, 
        lazy="selectin"
    )
    AnnotationTagLinks: Mapped[List["AnnotationTagLink"]] = relationship(
        "eyened_orm.tag.AnnotationTagLink",
        back_populates="Tag", 
        passive_deletes=True, 
        lazy="selectin"
    )
    SegmentationTagLinks: Mapped[List["SegmentationTagLink"]] = relationship(
        "eyened_orm.tag.SegmentationTagLink",
        back_populates="Tag", 
        passive_deletes=True, 
        lazy="selectin"
    )
    FormAnnotationTagLinks: Mapped[List["FormAnnotationTagLink"]] = relationship(
        "eyened_orm.tag.FormAnnotationTagLink",
        back_populates="Tag", 
        passive_deletes=True, 
        lazy="selectin"
    )

    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", back_populates="Tags")


class StudyTagLink(Base):
    __tablename__ = "StudyTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Study", "StudyID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID", ondelete="CASCADE"), primary_key=True)
    StudyID: Mapped[int] = mapped_column(ForeignKey("Study.StudyID", ondelete="CASCADE"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship("eyened_orm.tag.Tag", back_populates="StudyTagLinks")
    Study: Mapped["Study"] = relationship("eyened_orm.study.Study", back_populates="StudyTagLinks")
    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", lazy="selectin")

class ImageInstanceTagLink(Base):
    __tablename__ = "ImageInstanceTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "ImageInstance", "ImageInstanceID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID", ondelete="CASCADE"), primary_key=True)
    ImageInstanceID: Mapped[int] = mapped_column(ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship("eyened_orm.tag.Tag", back_populates="ImageInstanceTagLinks")
    ImageInstance: Mapped["ImageInstance"] = relationship("eyened_orm.image_instance.ImageInstance", back_populates="ImageInstanceTagLinks")
    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", lazy="selectin")

class AnnotationTagLink(Base):
    __tablename__ = "AnnotationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Annotation", "AnnotationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID", ondelete="CASCADE"), primary_key=True)
    AnnotationID: Mapped[int] = mapped_column(ForeignKey("Annotation.AnnotationID", ondelete="CASCADE"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship("eyened_orm.tag.Tag", back_populates="AnnotationTagLinks")
    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", lazy="selectin")


class SegmentationTagLink(Base):
    __tablename__ = "SegmentationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Segmentation", "SegmentationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID", ondelete="CASCADE"), primary_key=True)
    SegmentationID: Mapped[int] = mapped_column(ForeignKey("Segmentation.SegmentationID", ondelete="CASCADE"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship("eyened_orm.tag.Tag", back_populates="SegmentationTagLinks")
    Segmentation: Mapped["Segmentation"] = relationship("eyened_orm.segmentation.Segmentation", back_populates="SegmentationTagLinks")
    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", lazy="selectin")


class FormAnnotationTagLink(Base):
    __tablename__ = "FormAnnotationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "FormAnnotation", "FormAnnotationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
    )
    TagID: Mapped[int] = mapped_column(ForeignKey("Tag.TagID", ondelete="CASCADE"), primary_key=True)
    FormAnnotationID: Mapped[int] = mapped_column(ForeignKey("FormAnnotation.FormAnnotationID", ondelete="CASCADE"), primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship("eyened_orm.tag.Tag", back_populates="FormAnnotationTagLinks")
    FormAnnotation: Mapped["FormAnnotation"] = relationship("eyened_orm.form_annotation.FormAnnotation", back_populates="FormAnnotationTagLinks")
    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", lazy="selectin")