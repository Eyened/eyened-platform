"""Membership reads and writes: the input to every scope resolution."""
from __future__ import annotations

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository
from eyened_orm.utils.factories import make_creator, make_project


def test_roles_for_returns_a_project_to_role_map(session):
    repo = ProjectMemberRepository(session)
    alice = make_creator(session, "alice")
    bob = make_creator(session, "bob")
    a = make_project(session, "A")
    b = make_project(session, "B")
    c = make_project(session, "C")
    repo.upsert(alice.CreatorID, a.ProjectID, ProjectRole.grader)
    repo.upsert(alice.CreatorID, b.ProjectID, ProjectRole.read_only)
    repo.upsert(bob.CreatorID, c.ProjectID, ProjectRole.project_admin)
    alice_id, a_id, b_id = alice.CreatorID, a.ProjectID, b.ProjectID
    session.commit()
    session.expunge_all()

    assert ProjectMemberRepository(session).roles_for(alice_id) == {
        a_id: ProjectRole.grader,
        b_id: ProjectRole.read_only,
    }


def test_upsert_reports_the_previous_role_so_the_caller_can_audit_a_change(session):
    repo = ProjectMemberRepository(session)
    alice = make_creator(session, "alice")
    a = make_project(session, "A")

    _, previous = repo.upsert(alice.CreatorID, a.ProjectID, ProjectRole.read_only)
    assert previous is None
    member, previous = repo.upsert(alice.CreatorID, a.ProjectID, ProjectRole.grader)
    assert previous is ProjectRole.read_only
    assert member.Role is ProjectRole.grader


def test_roles_for_a_creator_with_no_memberships_is_empty(session):
    alice = make_creator(session, "alice")
    session.commit()
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {}
