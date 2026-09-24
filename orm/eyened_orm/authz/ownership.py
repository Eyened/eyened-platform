"""The ownership overlay on annotation mutations.

Deliberately **outside** ``effective_role``, because it is not role-derived.
That is what makes v0.3's "modify other users' annotations -- cross" true for
read_only, grader and project_admin simultaneously, and for an administrator.
"""
from __future__ import annotations

from collections.abc import Set

from .errors import PermissionDeniedError
from .roles import ProjectRole
from .scope import AccessScope

__all__ = ["require_owner", "require_owner_or_project_admin"]


def require_owner(
    scope: AccessScope,
    *,
    owner_id: int | None,
    entity: str,
    entity_id: int | None,
    projects: Set[int],
) -> None:
    """Modify: only the author. 403 for everyone else, administrators included.

    A NULL author matches nobody, so such a row is permanently unmodifiable --
    intended, and the reason ModelSegmentation (which carries no CreatorID at
    all) is exempt from this overlay entirely rather than passed through it.

    Always 403, never 404, and that rests on a precondition every current
    caller meets: the row passed the read scope and the role floor before
    reaching here, so it is a visible row with a refused action. A caller
    fetching unscoped, or with no floor in front of it, would owe a 404
    instead and must not simply reuse this.
    """
    if owner_id is None or owner_id != scope.actor_id:
        raise PermissionDeniedError(
            actor_id=scope.actor_id,
            entity=entity,
            entity_id=entity_id,
            projects=projects,
        )


def require_owner_or_project_admin(
    scope: AccessScope,
    *,
    owner_id: int | None,
    entity: str,
    entity_id: int | None,
    projects: Set[int],
) -> None:
    """Delete: the author, or a project_admin in every project it touches.

    An administrator passes without a separate clause here, but by one of *two*
    mechanisms depending on what ``projects`` resolved to: an empty set is
    caught by ``AccessScope.require``'s fail-closed guard, whose ``is_admin``
    arm lets them through before any role is looked up, and a non-empty one
    reaches ``effective_role``'s short-circuit. Naming only the second would be
    wrong for exactly the case -- an entity that touches no project -- where the
    difference between an administrator and everyone else is a 204 and a 404.
    """
    if owner_id is not None and owner_id == scope.actor_id:
        return
    scope.require(
        projects, ProjectRole.project_admin, entity=entity, entity_id=entity_id
    )
