"""Membership operations: idempotent, audited, and never silently lossy."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from eyened_orm import AuditLog
from eyened_orm.authz.administration import grant, parse_role, revoke
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository
from eyened_orm.utils.factories import make_creator, make_project


def test_parse_role_accepts_every_role_name():
    """All three, not a sample: the CLI's vocabulary is the enum's."""
    assert {name: parse_role(name) for name in ("read_only", "grader", "project_admin")} == {
        "read_only": ProjectRole.read_only,
        "grader": ProjectRole.grader,
        "project_admin": ProjectRole.project_admin,
    }


def test_parse_role_names_the_valid_roles_on_a_bad_value():
    """Fails at the CLI boundary rather than surfacing a bare ValueError.

    Everything past the parse deals in the enum, so no downstream code
    compares role strings.
    """
    with pytest.raises(ValueError) as exc:
        parse_role("admin")
    for name in ("read_only", "grader", "project_admin"):
        assert name in str(exc.value)


def test_grant_creates_a_membership_and_audits_it(session):
    make_creator(session, "alice")
    make_project(session, "A")
    session.commit()

    result = grant(session, username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()

    assert result.changed is True and result.previous is None
    rows = session.scalars(
        select(AuditLog).where(AuditLog.Entity == "ProjectMember")
    ).all()
    assert len(rows) == 1
    assert rows[0].TrustedPath == "eorm grant"
    assert rows[0].ActorID is None
    assert rows[0].Action == "INSERT"
    assert rows[0].EntityID is None
    # AuditLog has no single integer id for a membership, so the pair rides in Changes.
    assert rows[0].Changes["project_name"] == "A"
    assert rows[0].Changes["role"] == "grader"


def test_an_unchanged_grant_writes_no_audit_row(session):
    make_creator(session, "alice")
    make_project(session, "A")
    grant(session, username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()

    result = grant(session, username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()

    assert result.changed is False
    assert len(session.scalars(select(AuditLog)).all()) == 1


def test_changing_a_role_records_old_and_new(session):
    make_creator(session, "alice")
    make_project(session, "A")
    grant(session, username="alice", project_name="A", role=ProjectRole.read_only)
    session.commit()

    result = grant(session, username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()

    assert result.previous is ProjectRole.read_only
    latest = session.scalars(select(AuditLog).order_by(AuditLog.AuditLogID.desc())).first()
    assert latest.Action == "UPDATE"
    assert latest.Changes["role"] == {"old": "read_only", "new": "grader"}


def test_revoke_removes_the_membership_and_audits_it(session):
    alice = make_creator(session, "alice")
    make_project(session, "A")
    grant(session, username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()

    assert revoke(session, username="alice", project_name="A") is True
    session.commit()
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {}

    removal = session.scalars(select(AuditLog).where(AuditLog.Action == "DELETE")).all()
    assert len(removal) == 1
    assert removal[0].TrustedPath == "eorm revoke"
    assert removal[0].Entity == "ProjectMember"
    assert removal[0].ActorID is None
    assert removal[0].EntityID is None
    assert removal[0].Changes["role"] == "grader"


def test_revoking_a_membership_that_does_not_exist_is_a_no_op(session):
    make_creator(session, "alice")
    make_project(session, "A")
    session.commit()
    assert revoke(session, username="alice", project_name="A") is False


def test_an_unknown_username_names_itself(session):
    make_project(session, "A")
    session.commit()
    with pytest.raises(LookupError, match="nosuchuser"):
        grant(session, username="nosuchuser", project_name="A", role=ProjectRole.grader)


def test_an_unknown_project_names_itself(session):
    """resolve_project's message is unpinned otherwise; only the creator's was."""
    make_creator(session, "alice")
    session.commit()
    with pytest.raises(LookupError, match="nosuchproject"):
        grant(session, username="alice", project_name="nosuchproject", role=ProjectRole.grader)


def test_a_plan_lists_what_will_be_granted_and_what_is_already_held(session, spanning):
    """Review before apply. "Grant Alice access to task 70" may resolve to eight
    projects, each handing over every patient, image and task in it --
    permanently, until revoked. An administrator who reads the command name and
    not the effect will over-grant."""
    from eyened_orm.authz.administration import plan_grant_for_tasks

    make_creator(session, "alice")
    grant(session, username="alice", project_name="A", role=ProjectRole.grader)
    session.commit()

    plan = plan_grant_for_tasks(
        session, username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    assert [name for _, name, _ in plan.to_grant] == ["B"]
    assert [name for _, name, _ in plan.already_held] == ["A"]


def test_a_plan_writes_nothing(session, spanning):
    from eyened_orm.authz.administration import plan_grant_for_tasks
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )

    alice = make_creator(session, "alice")
    session.commit()
    plan_grant_for_tasks(
        session, username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {}


def test_applying_a_plan_never_lowers_an_existing_role(session, spanning):
    """A user who is already project_admin in one of the task's projects keeps it."""
    from eyened_orm.authz.administration import apply_grant_plan, plan_grant_for_tasks
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )

    alice = make_creator(session, "alice")
    grant(session, username="alice", project_name="A", role=ProjectRole.project_admin)
    session.commit()

    plan = plan_grant_for_tasks(
        session, username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    apply_grant_plan(session, plan=plan)
    session.commit()

    roles = ProjectMemberRepository(session).roles_for(alice.CreatorID)
    assert roles[spanning["projects"]["A"]] is ProjectRole.project_admin
    assert roles[spanning["projects"]["B"]] is ProjectRole.grader


def test_a_lower_existing_role_is_upgraded_not_reported_as_already_held(
    session, spanning
):
    """`>= role` is the whole comparison: dropping the level check and keeping
    only 'has a membership' silently refuses the upgrade, and the administrator
    reads 'already holds read_only in A' as success."""
    from eyened_orm.authz.administration import plan_grant_for_tasks

    make_creator(session, "alice")
    grant(session, username="alice", project_name="A", role=ProjectRole.read_only)
    session.commit()

    plan = plan_grant_for_tasks(
        session, username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    assert [name for _, name, _ in plan.to_grant] == ["A", "B"]
    assert plan.already_held == ()


def test_a_task_touching_no_projects_grants_nothing(session, spanning):
    """Rather than reporting success for a no-op that, under vacuity, is a task
    everyone can already see."""
    from eyened_orm.authz.administration import plan_grant_for_tasks

    make_creator(session, "alice")
    session.commit()
    plan = plan_grant_for_tasks(
        session, username="alice", task_ids=[spanning["empty"]], role=ProjectRole.grader
    )
    assert plan.to_grant == () and plan.already_held == ()


def test_an_unknown_task_id_among_valid_ones_is_an_error_not_a_silent_drop(
    session, spanning
):
    """The MIXED case, deliberately, rather than an all-unknown one: a weaker
    guard written `if not found:` passes an all-unknown test while still
    happily granting the valid half, leaving the operator believing alice can
    work every task they typed when she can only work some of them. Only a bad
    id *among good ones* distinguishes the two guards. The message names only
    what the operator got wrong."""
    from eyened_orm.authz.administration import plan_grant_for_tasks

    make_creator(session, "alice")
    session.commit()
    with pytest.raises(LookupError) as excinfo:
        plan_grant_for_tasks(
            session,
            username="alice",
            task_ids=[spanning["task"], 999999],
            role=ProjectRole.grader,
        )
    assert str(excinfo.value) == "no task with id 999999"


def test_the_plan_uses_the_same_definition_enforcement_uses(session, spanning):
    """Two implementations of "which projects does this task touch" will drift,
    and the failure mode is an administrator granting a set that does not match
    what the API requires."""
    from eyened_orm import Task
    from eyened_orm.authz.administration import plan_grant_for_tasks
    from eyened_orm.authz.scoping import projects_of

    make_creator(session, "alice")
    session.commit()
    plan = plan_grant_for_tasks(
        session, username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    assert {pid for pid, _, _ in plan.to_grant} == projects_of(
        session, Task, spanning["task"]
    )


def test_applying_a_plan_audits_every_grant(session, spanning):
    """apply_grant_plan goes through `grant`, so each membership carries the
    trusted-path attribution. A loop that upserts directly would write the same
    rows with no audit trail at all."""
    from eyened_orm.authz.administration import apply_grant_plan, plan_grant_for_tasks

    make_creator(session, "alice")
    session.commit()
    plan = plan_grant_for_tasks(
        session, username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    apply_grant_plan(session, plan=plan)
    session.commit()

    rows = session.scalars(
        select(AuditLog).where(AuditLog.Entity == "ProjectMember")
    ).all()
    assert {r.Changes["project_name"] for r in rows} == {"A", "B"}
    assert {(r.ActorID, r.TrustedPath) for r in rows} == {(None, "eorm grant")}
