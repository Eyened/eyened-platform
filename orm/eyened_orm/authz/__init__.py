"""Framework-free authorization core.

Imported by the API, the ``eorm`` CLI, notebooks and RQ workers alike, so
nothing here may import ``fastapi`` or ``pydantic``. The server maps the error
classes to HTTP statuses; the ORM only raises them.
"""
from __future__ import annotations

from .bootstrap import BootstrapOutcome, count_admins, ensure_admin
from .errors import AuthorizationError, NotVisibleError, PermissionDeniedError
from .roles import ProjectRole
from .scope import AccessScope
from .scoping import PROJECT_IDS_OF, apply_scope, projects_of

__all__ = [
    "PROJECT_IDS_OF",
    "AccessScope",
    "AuthorizationError",
    "BootstrapOutcome",
    "NotVisibleError",
    "PermissionDeniedError",
    "ProjectRole",
    "apply_scope",
    "count_admins",
    "ensure_admin",
    "projects_of",
]
