"""Framework-free authorization core.

Imported by the API, the ``eorm`` CLI, notebooks and RQ workers alike, so
nothing here may import ``fastapi`` or ``pydantic``. The server maps the error
classes to HTTP statuses; the ORM only raises them.
"""
from __future__ import annotations

from .errors import AuthorizationError, NotVisibleError, PermissionDeniedError
from .roles import ProjectRole
from .scope import AccessScope

__all__ = [
    "AccessScope",
    "AuthorizationError",
    "NotVisibleError",
    "PermissionDeniedError",
    "ProjectRole",
]
