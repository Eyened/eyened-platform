from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Set

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyened_orm.base import Base, CompositeUniqueConstraint, ForeignKeyIndex

if TYPE_CHECKING:
    from eyened_orm import Creator, FormAnnotation, ImageInstance, Segmentation, Study


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
    TagID: Mapped[int] = mapped_column(
        # Deliberately CASCADE, unlike the five annotation links: a star is a
        # personal preference, not annotation data, so it must never *block* a
        # tag delete -- it just goes with it (spec §3.2.1).
        ForeignKey("Tag.TagID", ondelete="CASCADE"), primary_key=True
    )
    CreatorID: Mapped[int] = mapped_column(
        ForeignKey("Creator.CreatorID", ondelete="CASCADE"), primary_key=True
    )
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(
        "eyened_orm.tag.Tag", back_populates="CreatorTagLinks"
    )
    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", back_populates="StarredTags"
    )


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

    CreatorTagLinks: Mapped[Set["CreatorTagLink"]] = relationship(
        "eyened_orm.tag.CreatorTagLink",
        back_populates="Tag",
        passive_deletes=True,
        lazy="selectin",
    )

    StudyTagLinks: Mapped[Set["StudyTagLink"]] = relationship(
        "eyened_orm.tag.StudyTagLink",
        back_populates="Tag",
        passive_deletes=True,
        lazy="selectin",
    )
    ImageInstanceTagLinks: Mapped[Set["ImageInstanceTagLink"]] = relationship(
        "eyened_orm.tag.ImageInstanceTagLink",
        back_populates="Tag",
        passive_deletes=True,
        lazy="selectin",
    )
    AnnotationTagLinks: Mapped[Set["AnnotationTagLink"]] = relationship(
        "eyened_orm.tag.AnnotationTagLink",
        back_populates="Tag",
        passive_deletes=True,
        lazy="selectin",
    )
    SegmentationTagLinks: Mapped[Set["SegmentationTagLink"]] = relationship(
        "eyened_orm.tag.SegmentationTagLink",
        back_populates="Tag",
        passive_deletes=True,
        lazy="selectin",
    )
    FormAnnotationTagLinks: Mapped[Set["FormAnnotationTagLink"]] = relationship(
        "eyened_orm.tag.FormAnnotationTagLink",
        back_populates="Tag",
        passive_deletes=True,
        lazy="selectin",
    )

    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", back_populates="Tags"
    )


class StudyTagLink(Base):
    __tablename__ = "StudyTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Study", "StudyID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        Index("ix_StudyTag_Study_Tag", "StudyID", "TagID"),
    )
    TagID: Mapped[int] = mapped_column(
        # RESTRICT, not CASCADE: deleting a tag must never destroy applied-tag
        # annotation data (spec §3.2.1). Adopts the Segmentation.FeatureID
        # precedent, so every path is covered, not just the HTTP API.
        ForeignKey("Tag.TagID", ondelete="RESTRICT"), primary_key=True
    )
    StudyID: Mapped[int] = mapped_column(
        ForeignKey("Study.StudyID", ondelete="CASCADE"), primary_key=True
    )

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    Comment: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(
        "eyened_orm.tag.Tag", back_populates="StudyTagLinks"
    )
    Study: Mapped["Study"] = relationship(
        "eyened_orm.study.Study", back_populates="StudyTagLinks"
    )
    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", lazy="selectin"
    )


class ImageInstanceTagLink(Base):
    __tablename__ = "ImageInstanceTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "ImageInstance", "ImageInstanceID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        Index("ix_ImageInstanceTag_Image_Tag", "ImageInstanceID", "TagID"),
    )
    TagID: Mapped[int] = mapped_column(
        # RESTRICT, not CASCADE: deleting a tag must never destroy applied-tag
        # annotation data (spec §3.2.1). Adopts the Segmentation.FeatureID
        # precedent, so every path is covered, not just the HTTP API.
        ForeignKey("Tag.TagID", ondelete="RESTRICT"), primary_key=True
    )
    ImageInstanceID: Mapped[int] = mapped_column(
        ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE"),
        primary_key=True,
    )

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    Comment: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(
        "eyened_orm.tag.Tag", back_populates="ImageInstanceTagLinks"
    )
    ImageInstance: Mapped["ImageInstance"] = relationship(
        "eyened_orm.image_instance.ImageInstance",
        back_populates="ImageInstanceTagLinks",
    )
    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", lazy="selectin"
    )


class AnnotationTagLink(Base):
    __tablename__ = "AnnotationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Annotation", "AnnotationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        Index("ix_AnnotationTag_Annotation_Tag", "AnnotationID", "TagID"),
    )
    TagID: Mapped[int] = mapped_column(
        # RESTRICT, not CASCADE: deleting a tag must never destroy applied-tag
        # annotation data (spec §3.2.1). Adopts the Segmentation.FeatureID
        # precedent, so every path is covered, not just the HTTP API.
        ForeignKey("Tag.TagID", ondelete="RESTRICT"), primary_key=True
    )
    AnnotationID: Mapped[int] = mapped_column(
        ForeignKey("Annotation.AnnotationID", ondelete="CASCADE"), primary_key=True
    )

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(
        "eyened_orm.tag.Tag", back_populates="AnnotationTagLinks"
    )
    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", lazy="selectin"
    )


class SegmentationTagLink(Base):
    __tablename__ = "SegmentationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "Segmentation", "SegmentationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        Index("ix_SegmentationTag_Segmentation_Tag", "SegmentationID", "TagID"),
    )
    TagID: Mapped[int] = mapped_column(
        # RESTRICT, not CASCADE: deleting a tag must never destroy applied-tag
        # annotation data (spec §3.2.1). Adopts the Segmentation.FeatureID
        # precedent, so every path is covered, not just the HTTP API.
        ForeignKey("Tag.TagID", ondelete="RESTRICT"), primary_key=True
    )
    SegmentationID: Mapped[int] = mapped_column(
        ForeignKey("Segmentation.SegmentationID", ondelete="CASCADE"), primary_key=True
    )

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    Comment: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(
        "eyened_orm.tag.Tag", back_populates="SegmentationTagLinks"
    )
    Segmentation: Mapped["Segmentation"] = relationship(
        "eyened_orm.segmentation.Segmentation", back_populates="SegmentationTagLinks"
    )
    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", lazy="selectin"
    )


class FormAnnotationTagLink(Base):
    __tablename__ = "FormAnnotationTag"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Tag", "TagID"),
        ForeignKeyIndex(__tablename__, "FormAnnotation", "FormAnnotationID"),
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        Index(
            "ix_FormAnnotationTag_Form_Tag",
            "FormAnnotationID",
            "TagID",
        ),
    )
    TagID: Mapped[int] = mapped_column(
        # RESTRICT, not CASCADE: deleting a tag must never destroy applied-tag
        # annotation data (spec §3.2.1). Adopts the Segmentation.FeatureID
        # precedent, so every path is covered, not just the HTTP API.
        ForeignKey("Tag.TagID", ondelete="RESTRICT"), primary_key=True
    )
    FormAnnotationID: Mapped[int] = mapped_column(
        ForeignKey("FormAnnotation.FormAnnotationID", ondelete="CASCADE"),
        primary_key=True,
    )

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    Comment: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Tag: Mapped["Tag"] = relationship(
        "eyened_orm.tag.Tag", back_populates="FormAnnotationTagLinks"
    )
    FormAnnotation: Mapped["FormAnnotation"] = relationship(
        "eyened_orm.form_annotation.FormAnnotation",
        back_populates="FormAnnotationTagLinks",
    )
    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", lazy="selectin"
    )


#: Every ``Tag`` relationship whose target's primary key contains ``TagID``.
#:
#: Loading one of these makes the ORM's dependency processor try to blank out a
#: primary-key column when the tag is deleted, raising ``AssertionError`` before
#: any SQL is emitted -- which pre-empts the foreign keys and turns the intended
#: 409 into a 500 (spec §3.2.1). Every read that may precede a delete must
#: ``noload`` all of them; each one only protects its own collection.
#:
#: ``Tag.Creator`` is deliberately absent: its primary key is ``CreatorID``, it
#: is not a link collection, and ``DTOConverter.tag_to_get`` reads it.
#:
#: Bare attributes, deliberately -- **not** pre-built ``noload()`` options. Class
#: attribute access does not configure mappers, but constructing a loader option
#: does, and ``eyened_orm/__init__.py`` imports ``.tag`` at ``:13`` while
#: ``.segmentation`` (which ``SegmentationTagLink.Segmentation`` targets by
#: string) only arrives at ``:15``. A ``TAG_LINK_NOLOADS = (noload(...), ...)``
#: "optimisation" therefore raises ``InvalidRequestError`` at import time and
#: breaks the whole package. Verified empirically 2026-07-31.
#:
#: **This is a per-load guard, not a mapper-level one.** ``noload`` is a loader
#: option, and ``session.get()`` silently ignores its ``options`` on an
#: identity-map hit -- so the three call sites protect a *fresh* load only. A
#: ``Tag`` already in the Session, loaded earlier in the same request by
#: anything that did not pass these options, still carries its six collections
#: and still trips the assertion. The real fix -- mapper-level ``lazy="noload"``
#: on the six relationships below, which no call site can forget -- is
#: deliberately deferred, so treat every new read that may precede a delete as
#: needing this guard rather than assuming the hazard is closed.
TAG_LINK_COLLECTIONS = (
    Tag.CreatorTagLinks,
    Tag.StudyTagLinks,
    Tag.ImageInstanceTagLinks,
    Tag.AnnotationTagLinks,
    Tag.SegmentationTagLinks,
    Tag.FormAnnotationTagLinks,
)
