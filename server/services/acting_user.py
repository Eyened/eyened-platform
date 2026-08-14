from __future__ import annotations

from dataclasses import dataclass


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
