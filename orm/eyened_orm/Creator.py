from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, List

from sqlmodel import Field, Relationship
from sqlalchemy import Column, select, BINARY
from sqlalchemy.orm import Session

from .base import Base, PrivateField

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, SubTask


class CreatorBase(Base):
    CreatorName: str = Field(max_length=45, unique=True)
    EmployeeIdentifier: str | None = Field(max_length=255, default=None)
    # differentiates between AI models and human users
    IsHuman: bool
    # paths where the model can be found
    Path: str | None = Field(max_length=80, default=None)
    # the model's version
    Version: int | None
    # model/user description
    Description: str | None = Field(max_length=1000, default=None)
    # not used currently
    Role: int | None


class Creator(CreatorBase, table=True):
    """
    Represents a creator entity in the system, which can be either a human user or an AI model.
    Creators can perform annotations, form annotations, and subtasks.
    """

    __tablename__ = "Creator"

    _name_column: ClassVar[str] = "CreatorName"

    CreatorID: int | None = Field(default=None, primary_key=True)

    # Authentication and authorization
    # deprecated, use PasswordHash instead
    Password: bytes | None = PrivateField(sa_column=Column(BINARY(32)))
    # user's password
    PasswordHash: str | None = PrivateField(max_length=255)

    # creation timestamp
    DateInserted: datetime = Field(default_factory=datetime.now)

    # Relationships
    Annotations: List["Annotation"] = Relationship(back_populates="Creator")
    FormAnnotations: List["FormAnnotation"] = Relationship(back_populates="Creator")
    SubTasks: List["SubTask"] = Relationship(back_populates="Creator")
