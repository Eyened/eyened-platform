from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eyened_orm.authz.scope import AccessScope


@dataclass(frozen=True)
class ActingUser:
    """The authenticated user performing a service operation.

    A framework-agnostic value object so Services never import ``CurrentUser``
    from the routes/handler layer (which would invert the API -> Service
    dependency arrow). Routes build this from their ``CurrentUser``; the
    Service uses it for audit logging now and for Step 2 authz later.
    """

    id: int
    username: str

    @classmethod
    def from_scope(cls, scope: "AccessScope") -> "ActingUser":
        """Derive the audit identity from the request's scope.

        The Service used ``ActingUser`` for audit logging and now uses
        ``AccessScope`` for authorization; both name the same actor, so the
        scope is the single source and this is the projection AuditService
        wants.
        """
        return cls(id=scope.actor_id, username=scope.username)
