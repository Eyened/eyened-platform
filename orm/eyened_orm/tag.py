from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from eyened_orm.base import Base, ForeignKeyIndex

if TYPE_CHECKING:
    pass

class Tag(Base):
    __tablename__ = "Tag"
    TagID: Mapped[int] = mapped_column(primary_key=True)
    TagName: Mapped[str] = mapped_column(String(256), unique=True)


tag_annotation_association_table = Table(
    "AnnotationTag",
    Base.metadata,
    Column("TagID", ForeignKey("Tag.TagID"), nullable=False),
    Column(
        "AnnotationID",
        ForeignKey("Annotation.AnnotationID"),
        nullable=False),
    ForeignKeyIndex("AnnotationTag", "Annotation", "AnnotationID"),
    ForeignKeyIndex("AnnotationTag", "Tag", "TagID"),
)

tag_study_association_table = Table(
    "StudyTag",
    Base.metadata,
    Column("TagID", ForeignKey("Tag.TagID"), nullable=False),
    Column("StudyID", ForeignKey("Study.StudyID"), nullable=False),
    ForeignKeyIndex("StudyTag", "Tag", "TagID"),
    ForeignKeyIndex("StudyTag", "Study", "StudyID"),
)

tag_image_instance_association_table = Table(
    "ImageInstanceTag",
    Base.metadata,
    Column("TagID", ForeignKey("Tag.TagID"), nullable=False),
    Column("ImageInstanceID",
        ForeignKey("ImageInstance.ImageInstanceID"),
        nullable=False),
    ForeignKeyIndex("ImageInstanceTag", "Tag", "TagID"),
    ForeignKeyIndex("ImageInstanceTag", "ImageInstance", "ImageInstanceID"),
)
