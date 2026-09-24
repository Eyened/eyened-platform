"""The one way a repository reads a single row under a scope.

``Session.get`` consults the identity map and can return a row without issuing
a query at all, so a row already loaded this request would come back
unfiltered. Every scoped read goes through a ``select`` instead.
"""
from __future__ import annotations

from typing import Any, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authz.scope import AccessScope
from ..authz.scoping import SET_VALUED_ENTITIES, SINGLE_PROJECT_ENTITIES, apply_scope
from ..base import Base

__all__ = ["scoped_one"]

# Generic, so a repository's `-> Patient | None` stays the *declared* return
# type at the call site, even though nothing enforces it: `apply_scope` is
# typed `-> Select` unparameterized, so this isn't a checked guarantee -- a
# bare `-> Base | None` would just make that erasure explicit and force a
# cast into each of the ~20 call sites instead.
T = TypeVar("T", bound=Base)


def scoped_one(
    session: Session,
    entity: type[T],
    scope: AccessScope,
    *criteria: Any,
    options: Sequence[Any] = (),
) -> T | None:
    """Return the one row of ``entity`` matching ``criteria`` the scope may read.

    ``None`` when it does not exist *or* is out of scope -- deliberately
    indistinguishable, so the service's existing NotFoundError produces the 404
    and no caller can tell the two apart.

    Raises ``KeyError`` for an entity with no scoping rule. ``apply_scope``
    raises only for an entity in none of its three registries --
    ``SAFE_UNFILTERED_ENTITIES`` is a fallback this check does not have. So
    this check fires on a larger set: an entity that is safe-unfiltered but
    neither single- nor set-valued raises right here, before ``apply_scope``
    is ever reached. It is also unconditional, where ``apply_scope``
    short-circuits an admin scope ahead of any registry lookup.
    """
    if entity not in SINGLE_PROJECT_ENTITIES and entity not in SET_VALUED_ENTITIES:
        raise KeyError(
            f"{entity.__name__} has no scoping rule; scoped_one would not filter it"
        )
    stmt = select(entity).where(*criteria)
    if options:
        stmt = stmt.options(*options)
    return session.scalars(apply_scope(stmt, entity, scope)).first()
