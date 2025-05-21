from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship
from sqlalchemy import Column, select
from sqlalchemy.dialects.mysql import BINARY, CHAR
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

    # Primary identifiers
    CreatorID: int = Field(primary_key=True)
    CreatorName: str = Field(max_length=45, unique=True)  # username in the application

    # User/Model attributes
    # to be removed/renamed (employee number/code)
    MSN: Optional[str] = Field(default=None, sa_column=Column(CHAR(6)))
    
    # differentiates between AI models and human users
    IsHuman: bool

    # paths where the model can be found
    Path: Optional[str] = Field(default=None, max_length=80)

    # model/user description
    Description: Optional[str] = Field(default=None, max_length=1000)

    # the model's version
    Version: Optional[int]

    # Authentication and authorization
    # user's password
    Password: Optional[bytes] = Field(default=None, sa_column=Column(BINARY(32)))
    #PasswordHash: Optional[str] = Field(default=None, max_length=255)
    
    # not used currently
    Role: Optional[int]

    # creation timestamp
    DateInserted: datetime = Field(default_factory=datetime.now)

    # Relationships
    Annotations: List["Annotation"] = Relationship(back_populates="Creator")
    FormAnnotations: List["FormAnnotation"] = Relationship(back_populates="Creator")
    SubTasks: List["SubTask"] = Relationship(back_populates="Creator")

    def __repr__(self) -> str:
        return f"{self.CreatorID}: {self.CreatorName}"

    @classmethod
    def get_columns(cls):
        """
        Get all columns except for sensitive ones (Password).

        This overrides the method in Base and ensures that to_dict() and 
        to_list() do not include the password.
        """
        return [c for c in cls.__fields__ if c not in ["Password"]]

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional["Creator"]:
        """Find a creator by their name (CreatorName)."""
        return session.scalar(select(cls).where(cls.CreatorName == name))

    @classmethod
    def name_to_id(cls, session: Session) -> dict[str, int]:
        """Get a mapping of creator names to their IDs."""
        return {
            creator.CreatorName: creator.CreatorID
            for creator in session.scalars(select(cls)).all()
        }
