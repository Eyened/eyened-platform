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
from ..authz.scoping import apply_scope
from ..base import Base

__all__ = ["scoped_one"]

# Generic, so a repository's `-> Patient | None` still typechecks. A bare
# `-> Base | None` would erase the concrete type at every one of the ~20 call
# sites and push a cast into each of them.
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
    """
    stmt = select(entity).where(*criteria)
    if options:
        stmt = stmt.options(*options)
    return session.scalars(apply_scope(stmt, entity, scope)).first()
