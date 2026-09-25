"""The project role hierarchy.

Its own module so the ``ProjectMember`` model can import it without dragging in
``AccessScope`` (which imports the error classes, which nothing in the model
layer needs).
"""
from __future__ import annotations

import enum

__all__ = ["ProjectRole", "parse_role"]


class ProjectRole(enum.IntEnum):
    """Ordered project privileges, lowest first.

    ``IntEnum`` gives ordering for free, so every check is written
    ``role >= floor`` rather than ``role in {...}`` -- a future privilege is
    additive and no call site is revisited. SQLAlchemy's ``Enum`` type persists
    the *name*, so the column holds ``'read_only' | 'grader' | 'project_admin'``
    and stays readable in the database.
    """

    read_only = 1
    grader = 2
    project_admin = 3


def parse_role(value: str) -> ProjectRole:
    """Convert a CLI string to a ProjectRole, naming the valid roles on failure.

    The conversion happens once, at the boundary; everything past it deals in
    the enum, so no downstream code compares role strings.

    Lives beside ``ProjectRole`` rather than on either administration class: it
    touches no repository, and the CLI calls it *before* a session is opened.
    """
    try:
        return ProjectRole[value]
    except KeyError:
        valid = ", ".join(r.name for r in ProjectRole)
        raise ValueError(f"unknown role {value!r}; valid roles are: {valid}") from None
