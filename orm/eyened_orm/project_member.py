from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, ForeignKeyIndex

__all__ = ["ProjectMember", "ProjectRole"]


class ProjectRole(enum.IntEnum):
    """Ordered project roles: checks read ``role >= ProjectRole.grader``.

    Each higher role is a strict superset of the one below, so future privileges
    are additive and no call site is revisited. ``IntEnum`` buys the ordering;
    ``SAEnum`` persists the member *name*, so the column reads as 'grader' in SQL.
    """

    read_only = 1
    grader = 2
    project_admin = 3


class ProjectMember(Base):
    """One row = one creator's role in one project. No row = no access.

    Two requirements are made structural rather than validated in the API:
    'exactly one role per project' is the **primary key**, and 'granting access
    must assign a role' is a non-Optional column. Revocation is row deletion, not
    a flag -- that is what makes a revocation take effect on the next request,
    with no extra predicate.
    """

    __tablename__ = "ProjectMember"
    __table_args__ = (
        # Duplicates the clustered PK's leading prefix, so InnoDB does not need it
        # for the FK. Declared anyway for house consistency (cf. StudyTag's TagID).
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        ForeignKeyIndex(__tablename__, "Project", "ProjectID"),
    )

    # PK order is (CreatorID, ProjectID), not the reverse: the scope is resolved
    # on every request with `where(CreatorID == actor_id)`, which this makes one
    # index seek over 0-5 rows. Reversed, the hottest query in the system is a scan.
    CreatorID: Mapped[int] = mapped_column(
        ForeignKey("Creator.CreatorID", ondelete="RESTRICT"), primary_key=True
    )
    ProjectID: Mapped[int] = mapped_column(
        ForeignKey("Project.ProjectID", ondelete="CASCADE"), primary_key=True
    )
    Role: Mapped[ProjectRole] = mapped_column(SAEnum(ProjectRole))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())
