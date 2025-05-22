from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, List

from sqlmodel import Field, Relationship
from sqlalchemy import Column, select, BINARY
from sqlalchemy.orm import Session

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, SubTask


class Creator(Base, table=True):
    """
    Represents a creator entity in the system, which can be either a human user or an AI model.
    Creators can perform annotations, form annotations, and subtasks.
    """

    __tablename__ = "Creator"

    _name_column: ClassVar[str] = "CreatorName"

    # Primary identifiers
    CreatorID: int = Field(primary_key=True)
    CreatorName: str = Field(max_length=45, unique=True)  # username in the application
    EmployeeIdentifier: str | None = Field(max_length=255)  # employee number/code

    # differentiates between AI models and human users
    IsHuman: bool

    # paths where the model can be found
    Path: str | None = Field(max_length=80)

    # model/user description
    Description: str | None = Field(max_length=1000)

    # the model's version
    Version: int | None

    # Authentication and authorization
    # deprecated, use PasswordHash instead
    Password: bytes | None = Field(sa_column=Column(BINARY(32)))
    # user's password
    PasswordHash: str | None = Field(max_length=255)

    # not used currently
    Role: int | None

    # creation timestamp
    DateInserted: datetime = Field(default_factory=datetime.now)

    # Relationships
    Annotations: List["Annotation"] = Relationship(back_populates="Creator")
    FormAnnotations: List["FormAnnotation"] = Relationship(back_populates="Creator")
    SubTasks: List["SubTask"] = Relationship(back_populates="Creator")

    @classmethod
    def columns(cls):
        """
        Get all columns except for sensitive ones (Password).

        This overrides the method in Base and ensures that to_dict() and
        to_list() do not include the password.
        """
        return [c for c in super().columns() if c.name not in ["Password", "PasswordHash"]]
