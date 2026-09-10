"""The project role hierarchy.

Its own module so the ``ProjectMember`` model can import it without dragging in
``AccessScope`` (which imports the error classes, which nothing in the model
layer needs).
"""
from __future__ import annotations

import enum

__all__ = ["ProjectRole"]


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
