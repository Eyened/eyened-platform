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

__all__ = [
    "AdminEntityNotFound",
    "AuthorizationError",
    "NotVisibleError",
    "PermissionDeniedError",
]


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


class AdminEntityNotFound(Exception):
    """An administration call named a creator, project or task that does not exist.

    Deliberately **not** ``LookupError``: that is the base class of ``KeyError``
    and ``IndexError``, so catching it to build a 404 -- or, in the CLI, a clean
    ``ClickException`` -- silently converts any dict or list miss inside the
    call into "not found".

    Deliberately not an ``AuthorizationError`` either: nothing here is a denial,
    and the 404 policy that keeps an ``AuthorizationError``'s detail out of the
    response body does not apply. The message names the missing entity, and the
    CLI prints it verbatim via ``ClickException(str(exc))``.

    ``entity`` is carried separately from the message for the reason this
    module's own docstring gives about ``AuthorizationError``: a bare
    ``class ...: ...`` satisfies the status mapping and leaves nobody able to
    answer *which* lookup failed. Step 2 maps this to a 404 whose body says
    nothing, so the one fact the handler cannot recover from a formatted string
    is the one that goes here. It is a separate argument rather than an
    interpolation because the three messages do not share a shape -- two read
    "no X named Y", the task one reads "no task with ids A, B".
    """

    def __init__(self, message: str, *, entity: str) -> None:
        self.entity = entity
        super().__init__(message)
