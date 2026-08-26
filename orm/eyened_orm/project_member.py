from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from .authz.roles import ProjectRole
from .base import Base

__all__ = ["ProjectMember"]


class ProjectMember(Base):
    """A creator's role in one project.

    The composite primary key structurally enforces v0.3's "a user is assigned
    exactly one role per project" rather than leaving it to a uniqueness check,
    and it is the only index the table needs at a ~185-row steady state.

    ``AuditLog`` has no single integer id for a membership, so membership
    records carry the pair in ``Changes`` and leave ``EntityID`` NULL.
    """

    __tablename__ = "ProjectMember"

    CreatorID: Mapped[int] = mapped_column(
        ForeignKey("Creator.CreatorID", ondelete="RESTRICT"), primary_key=True
    )
    ProjectID: Mapped[int] = mapped_column(
        ForeignKey("Project.ProjectID", ondelete="CASCADE"), primary_key=True
    )
    Role: Mapped[ProjectRole] = mapped_column(SAEnum(ProjectRole), nullable=False)
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())
