from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BINARY, CHAR, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, SubTask


class Creator(Base):
    """
    Represents a creator entity in the system, which can be either a human user or an AI model.
    Creators can perform annotations, form annotations, and subtasks.
    """
    __tablename__ = "Creator"

    # Primary identifiers
    CreatorID: Mapped[int] = mapped_column(primary_key=True)
    CreatorName: Mapped[str] = mapped_column(
        String(45), unique=True)  # username in the application

    # User/Model attributes

    # to be removed/renamed (employee number/code)
    MSN: Mapped[Optional[str]] = mapped_column(CHAR(6))

    # differentiates between AI models and human users
    IsHuman: Mapped[bool]

    # paths where the model can be found
    Path: Mapped[Optional[str]] = mapped_column(String(80))

    # model/user description
    Description: Mapped[Optional[str]] = mapped_column(String(1000))

    # the model's version
    Version: Mapped[Optional[int]]

    # Authentication and authorization
    # user's password
    Password: Mapped[Optional[bytes]] = mapped_column(BINARY(32))
    # not used currently
    Role: Mapped[Optional[int]]

    # creation timestamp
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    Annotations: Mapped[List[Annotation]] = relationship(
        back_populates="Creator")
    FormAnnotations: Mapped[List[FormAnnotation]] = relationship(
        back_populates="Creator")
    SubTasks: Mapped[List[SubTask]] = relationship(
        back_populates="Creator")

    def __repr__(self) -> str:
        return f"{self.CreatorID}: {self.CreatorName}"

    @classmethod
    def get_columns(cls):
        """
        Get all columns except for sensitive ones (Password).

        This overrides the method in Base and ensures that to_dict() and 
        to_list() do not include the password.
        """
        return [c for c in super().get_columns() if c.name not in ["Password"]]

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional[Creator]:
        """Find a creator by their name (CreatorName)."""
        return session.scalar(select(cls).where(cls.CreatorName == name))

    @classmethod
    def name_to_id(cls, session: Session) -> dict[str, int]:
        """Get a mapping of creator names to their IDs."""
        return {
            creator.CreatorName: creator.CreatorID
            for creator in cls.fetch_all(session)
        }
