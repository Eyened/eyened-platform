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


class SegmentationTag(Base, table=True):
    __tablename__ = "SegmentationTag"
    __table_args__ = (
        Index("fk_SegmentationTag_Tag1_idx", "TagID"),
        Index("fk_SegmentationTag_Segmentation1_idx", "SegmentationID"),
    )
    
    TagID: int = Field(foreign_key="Tag.TagID", primary_key=True)
    SegmentationID: int = Field(foreign_key="Segmentation.SegmentationID", primary_key=True)   


class FormAnnotationTag(Base, table=True):
    __tablename__ = "FormAnnotationTag"
    __table_args__ = (
        Index("fk_FormAnnotationTag_Tag1_idx", "TagID"),
        Index("fk_FormAnnotationTag_FormAnnotation1_idx", "FormAnnotationID"),
    )

    TagID: int = Field(foreign_key="Tag.TagID", primary_key=True)
    FormAnnotationID: int = Field(foreign_key="FormAnnotation.FormAnnotationID", primary_key=True)


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
