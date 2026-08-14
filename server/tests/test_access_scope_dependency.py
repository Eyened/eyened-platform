"""get_access_scope: from the database, per request, and 401 for the deactivated."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository
from eyened_orm.utils.factories import make_creator, make_project
from server.routes.auth import CurrentUser
from server.services.access_scope import get_access_scope


def test_scope_carries_the_memberships_held_at_request_time(session):
    alice = make_creator(session, "alice")
    a = make_project(session, "A")
    ProjectMemberRepository(session).upsert(
        alice.CreatorID, a.ProjectID, ProjectRole.grader
    )
    session.commit()

    scope = get_access_scope(
        current_user=CurrentUser(creator_id=alice.CreatorID, username="alice"),
        db=session,
    )
    assert scope.is_admin is False
    assert scope.actor_id == alice.CreatorID
    assert scope.username == "alice"
    assert scope.effective_role(a.ProjectID) is ProjectRole.grader


def test_a_revocation_takes_effect_on_the_next_request_without_a_new_login(session):
    alice = make_creator(session, "alice")
    a = make_project(session, "A")
    repo = ProjectMemberRepository(session)
    repo.upsert(alice.CreatorID, a.ProjectID, ProjectRole.grader)
    session.commit()

    user = CurrentUser(creator_id=alice.CreatorID, username="alice")
    assert get_access_scope(current_user=user, db=session).effective_role(a.ProjectID)

    repo.delete(repo.get(alice.CreatorID, a.ProjectID))
    session.commit()
    assert get_access_scope(current_user=user, db=session).effective_role(a.ProjectID) is None


def test_an_administrator_gets_is_admin_and_no_rows(session):
    from eyened_orm.authz.bootstrap import ensure_admin

    root, _ = ensure_admin(session, "root", None)
    session.commit()
    scope = get_access_scope(
        current_user=CurrentUser(creator_id=root.CreatorID, username="root"), db=session
    )
    assert scope.is_admin is True
    assert scope.effective_role(4321) is ProjectRole.project_admin


def test_a_deactivated_user_is_rejected_rather_than_given_an_empty_scope(session):
    """An empty scope would still pass every check on a vacuous object.

    A deactivated user holding an unexpired token could then still create
    tasks, and modify and delete empty ones. v0.3 says they hold *no* access,
    so the check belongs here, before any scope object exists.
    """
    alice = make_creator(session, "alice")
    alice.Inactive = True
    session.commit()

    with pytest.raises(HTTPException) as exc:
        get_access_scope(
            current_user=CurrentUser(creator_id=alice.CreatorID, username="alice"),
            db=session,
        )
    assert exc.value.status_code == 401


def test_a_token_naming_a_deleted_creator_is_rejected(session):
    with pytest.raises(HTTPException) as exc:
        get_access_scope(
            current_user=CurrentUser(creator_id=999_999, username="ghost"), db=session
        )
    assert exc.value.status_code == 401
