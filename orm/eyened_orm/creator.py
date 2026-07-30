import enum
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, List, Optional, Set

from sqlalchemy import BINARY, ForeignKey, String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, SubTask, Segmentation, Tag, CreatorTagLink, Task


class SystemRole(enum.IntEnum):
    """Global system role, stored in the pre-existing ``Creator.Role`` integer column.

    ``system_admin`` is a **data superuser**: it administers users, project access
    and project metadata *and* has full data access to every project. The control
    on it is attribution and audit, not denial.

    P2 deliberately keeps ``Creator.Role`` an untyped ``Optional[int]`` -- converting
    it to a ``SAEnum`` column with a ``NOT NULL`` default is enforcement-phase work,
    and these integer values are forward-compatible with it.
    """

    user = 0
    system_admin = 1


def is_system_admin(creator: "Creator") -> bool:
    """True only for an explicit system_admin. NULL (every row pre-cutover) -> False."""
    return creator.Role == SystemRole.system_admin


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

    # Deactivation, not deletion: ~99k FK rows make a hard delete impossible. A
    # deactivated creator cannot authenticate but keeps their authored work
    # attributed and their memberships retained-but-inert, so reactivation
    # restores prior access in one click.
    Inactive: Mapped[bool] = mapped_column(default=False)

    # Authentication (private)
    Password: Mapped[Optional[bytes]] = mapped_column(BINARY(32), info={"private": True})
    PasswordHash: Mapped[Optional[str]] = mapped_column(String(255), info={"private": True})

    # Timestamps
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    Annotations: Mapped[List["Annotation"]] = relationship("eyened_orm.annotation.Annotation", back_populates="Creator")
    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship("eyened_orm.form_annotation.FormAnnotation", back_populates="Creator")
    SubTasks: Mapped[List["SubTask"]] = relationship("eyened_orm.task.SubTask", back_populates="Creator")
    Segmentations: Mapped[List["Segmentation"]] = relationship("eyened_orm.segmentation.Segmentation", back_populates="Creator")
    Tags: Mapped[List["Tag"]] = relationship("eyened_orm.tag.Tag", back_populates="Creator")
    Tasks: Mapped[List["Task"]] = relationship("eyened_orm.task.Task", back_populates="Creator")
    # Tags that this creator starred
    StarredTags: Mapped[Set["CreatorTagLink"]] = relationship("eyened_orm.tag.CreatorTagLink", back_populates="Creator", viewonly=True, lazy="selectin")
