"""Authorization failures, raised by the ORM and mapped by the server.

Repositories live in ``orm/eyened_orm/repositories/``, which the CLI, ``eorm``,
notebooks and RQ workers all import. Raising ``HTTPException`` there would put
FastAPI in the ORM's import path and hand non-API callers an object they cannot
use -- so the ORM raises these and ``server/services/exceptions.py`` maps them.

The exception is verbose; the response is not. A bare ``class ...: ...`` would
satisfy the status mapping and leave nobody able to answer "why did Alice get a
404?". The actor, the object and the projects that failed are exactly the facts
a support question needs, and the 404 policy guarantees they can never be in the
response body -- so they go here, and into the denial log line at the handler.
"""
from __future__ import annotations

from collections.abc import Set as AbstractSet

__all__ = ["AuthorizationError", "NotVisibleError", "PermissionDeniedError"]


class AuthorizationError(Exception):
    """Raised when a scope may not perform an action.

    Carries the actor, the entity and the projects that failed, for the log.
    None of it reaches the client -- see the status handler.
    """

    def __init__(
        self,
        *,
        actor_id: int,
        entity: str,
        entity_id: int | None,
        projects: AbstractSet[int],
    ) -> None:
        self.actor_id = actor_id
        self.entity = entity
        self.entity_id = entity_id
        self.projects = frozenset(projects)
        super().__init__(
            f"actor={actor_id} entity={entity} entity_id={entity_id} "
            f"projects={sorted(self.projects)}"
        )


class NotVisibleError(AuthorizationError):
    """The actor is missing at least one of the object's projects -> 404.

    ``projects`` holds the missing ones.
    """


class PermissionDeniedError(AuthorizationError):
    """The actor holds every project but sits under the floor -> 403.

    ``projects`` holds the ones whose role was too low.
    """
