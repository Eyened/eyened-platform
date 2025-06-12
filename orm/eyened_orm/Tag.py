from typing import ClassVar
from sqlalchemy import Index
from sqlmodel import Field
from .base import Base

class TagBase(Base):
    TagName: str = Field(max_length=256, unique=True)

class Tag(TagBase, table=True):
    __tablename__ = "Tag"
    _name_column: ClassVar[str] = "TagName"

    TagID: int = Field(primary_key=True)


class AnnotationTag(Base, table=True):
    __tablename__ = "AnnotationTag"
    __table_args__ = (
        Index("fk_AnnotationTag_Tag1_idx", "TagID"),
        Index("fk_AnnotationTag_Annotation1_idx", "AnnotationID"),
    )

    TagID: int = Field(foreign_key="Tag.TagID", primary_key=True)
    AnnotationID: int = Field(foreign_key="Annotation.AnnotationID", primary_key=True)


class StudyTag(Base, table=True):
    __tablename__ = "StudyTag"
    __table_args__ = (
        Index("fk_StudyTag_Tag1_idx", "TagID"),
        Index("fk_StudyTag_Study1_idx", "StudyID"),
    )

    TagID: int = Field(foreign_key="Tag.TagID", primary_key=True)
    StudyID: int = Field(foreign_key="Study.StudyID", primary_key=True)


class ImageInstanceTag(Base, table=True):
    __tablename__ = "ImageInstanceTag"
    __table_args__ = (
        Index("fk_ImageInstanceTag_Tag1_idx", "TagID"),
        Index("fk_ImageInstanceTag_ImageInstance1_idx", "ImageInstanceID"),
    )

    TagID: int = Field(foreign_key="Tag.TagID", primary_key=True)
    ImageInstanceID: int = Field(
        foreign_key="ImageInstance.ImageInstanceID", primary_key=True
    )
