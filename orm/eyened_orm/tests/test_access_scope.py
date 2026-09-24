"""AccessScope: the containment rule, and the two traps that typecheck cleanly."""
from __future__ import annotations

import pytest

from eyened_orm.authz.errors import NotVisibleError, PermissionDeniedError
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope


def _member(**roles: ProjectRole) -> AccessScope:
    return AccessScope(
        actor_id=7,
        username="alice",
        is_admin=False,
        roles={int(k[1:]): v for k, v in roles.items()},
    )


def test_a_scope_cannot_be_built_positionally():
    """The escalation guard matches ``is_admin=`` keywords, so nothing else may exist.

    Before ``kw_only=True``, ``AccessScope(9, "mallory", True)`` built an
    unbounded scope that
    ``test_only_the_allow_listed_files_decide_a_scopes_admin_flag`` could not
    see -- it walks ``node.keywords``, and a positional argument is in
    ``node.args``. Widening the guard to inspect positions would still need it
    to know which position ``is_admin`` occupies; deleting the shape from the
    language does not. This test is the only thing standing between a future
    ``kw_only`` removal and a silently reopened door, so it asserts the
    constructor, not the guard.
    """
    with pytest.raises(TypeError):
        AccessScope(9, "mallory", True)  # type: ignore[misc]


def test_effective_role_short_circuits_for_an_administrator():
    """An admin's power is the short-circuit, not a row set."""
    admin = AccessScope(actor_id=1, username="root", is_admin=True, roles={})
    assert admin.effective_role(999) is ProjectRole.project_admin


def test_project_ids_raises_for_an_administrator():
    """It would return the empty set, giving an admin access to *nothing*.

    A comment is not a guard: any caller that builds a predicate from this
    without repeating the short-circuit silently locks the administrator out,
    and ``AbstractSet[int]`` warns nobody.
    """
    admin = AccessScope(actor_id=1, username="root", is_admin=True, roles={})
    with pytest.raises(TypeError, match="unbounded"):
        admin.project_ids


def test_roles_cannot_be_mutated_through_the_builders_handle():
    """frozen=True freezes the reference, not the dict behind it."""
    live = {1: ProjectRole.read_only}
    scope = AccessScope(actor_id=7, username="alice", is_admin=False, roles=live)
    live[2] = ProjectRole.project_admin
    assert scope.effective_role(2) is None
    with pytest.raises(TypeError):
        scope.roles[3] = ProjectRole.grader


def test_require_passes_when_every_project_reaches_the_floor():
    scope = _member(p1=ProjectRole.grader, p2=ProjectRole.project_admin)
    scope.require({1, 2}, ProjectRole.grader, entity="Task", entity_id=70)


def test_require_raises_not_visible_when_one_project_is_missing():
    """Containment: a single missing project fails the whole call -> 404."""
    scope = _member(p1=ProjectRole.project_admin)
    with pytest.raises(NotVisibleError) as exc:
        scope.require({1, 2}, ProjectRole.read_only, entity="Task", entity_id=70)
    assert exc.value.projects == {2}
    assert exc.value.entity_id == 70
    assert exc.value.actor_id == 7


def test_require_raises_permission_denied_when_a_role_is_under_the_floor():
    """Visible row, refused action -> 403."""
    scope = _member(p1=ProjectRole.grader, p2=ProjectRole.read_only)
    with pytest.raises(PermissionDeniedError) as exc:
        scope.require({1, 2}, ProjectRole.grader, entity="Task", entity_id=70)
    assert exc.value.projects == {2}


def test_require_on_an_empty_project_set_fails_closed_except_for_an_admin():
    """The inverse of read-side vacuity, and the admin exemption that saves it.

    v0.3 accepts vacuity for *visibility* (Visibility, consequence 4): an
    object touching no projects is findable by all. ``require`` is the write
    side, where the same emptiness would wave a zero-membership caller past
    every floor -- so it raises instead. The admin must still get through:
    ``effective_role`` short-circuits, but the empty set never reaches it, so
    the exemption has to sit ahead of the raise rather than behind it.
    """
    with pytest.raises(NotVisibleError):
        _member().require(set(), ProjectRole.project_admin, entity="Task", entity_id=3)
    AccessScope(actor_id=1, username="root", is_admin=True, roles={}).require(
        set(), ProjectRole.project_admin, entity="Task", entity_id=3
    )


def test_require_admin_refuses_a_project_admin():
    """A project_admin *is* a user in v0.3's platform matrix."""
    scope = _member(p1=ProjectRole.project_admin)
    with pytest.raises(PermissionDeniedError):
        scope.require_admin(entity="ImageInstance", entity_id=12)
