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
