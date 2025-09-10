from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, List, Optional

from sqlalchemy import BINARY, ForeignKey, String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, SubTask, Segmentation, Tag


class Creator(Base):
    """Represents a creator entity (human or AI model)."""

    __tablename__ = "Creator"

    _name_column: ClassVar[str] = "CreatorName"

    CreatorID: Mapped[int] = mapped_column(primary_key=True)

    # Identity and metadata
    CreatorName: Mapped[str] = mapped_column(String(45), unique=True)
    EmployeeIdentifier: Mapped[Optional[str]] = mapped_column(String(255))
    IsHuman: Mapped[bool] = mapped_column(Boolean)
    Path: Mapped[Optional[str]] = mapped_column(String(80))
    Version: Mapped[Optional[int]]
    Description: Mapped[Optional[str]] = mapped_column(String(1000))
    Role: Mapped[Optional[int]]

    # Authentication (private)
    Password: Mapped[Optional[bytes]] = mapped_column(BINARY(32), info={"private": True})
    PasswordHash: Mapped[Optional[str]] = mapped_column(String(255), info={"private": True})

    # Timestamps
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    Annotations: Mapped[List["Annotation"]] = relationship(back_populates="Creator")
    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship(back_populates="Creator")
    SubTasks: Mapped[List["SubTask"]] = relationship(back_populates="Creator")
    Segmentations: Mapped[List["Segmentation"]] = relationship(back_populates="Creator")
    Tags: Mapped[List["Tag"]] = relationship(back_populates="Creator")
