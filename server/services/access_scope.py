"""Resolve the request's AccessScope.

Sync ``def``, not ``async def``, and the distinction is not cosmetic: this runs
a database query on every request and the data layer is synchronous SQLAlchemy.
FastAPI runs a ``def`` dependency in a threadpool and an ``async def`` one
directly on the event loop, so declaring it async would block the loop once per
request. ``get_db`` is already a sync generator; this matches it. The rule to
hold: stay consistently sync along the whole call path rather than mixing,
which hides the blocking.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from eyened_orm import Creator
from eyened_orm.authz.scope import AccessScope
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository

from ..db import get_db
from ..routes.auth import CurrentUser, get_current_user


def get_access_scope(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccessScope:
    """The actor's admin flag and project-role map, read fresh from the database.

    Not from the JWT: a scope baked into a token would linger until expiry,
    which defeats a system whose stated job is revoking access on request.
    """
    creator = db.get(Creator, current_user.id)
    if creator is None or creator.Inactive:
        # Not an empty scope -- under vacuity an empty scope still passes every
        # check on an object touching no projects.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return AccessScope(
        actor_id=creator.CreatorID,
        username=creator.CreatorName,
        is_admin=bool(creator.IsAdmin),
        roles=ProjectMemberRepository(db).roles_for(creator.CreatorID),
    )
