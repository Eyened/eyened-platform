"""The CLI shell: tests for the things the shell adds over the functions.

Everything else is tested in test_authz_administration.py, which does not need
a real Database(). The accept path is not retested here: parse_role's happy
path is pinned there, and a CLI-level version of it could only assert that an
error string is *absent* from the output -- which is equally true of any
unrelated failure, so it would pass whether or not the parse ran.

`grant_all`'s confirmation prompt is tested here too, for the same reason:
`click.confirm(abort=True)` has no function-level equivalent, so only the CLI
shell can prove it actually gates the write.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from eyened_orm import AuditLog, ProjectMember
from eyened_orm.authz.administration import grant
from eyened_orm.authz.bootstrap import ensure_admin
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.commands import rbac as rbac_module
from eyened_orm.commands.rbac import (
    deactivate_cmd,
    grant_all_cmd,
    grant_cmd,
    grant_for_task_cmd,
    init_admin,
    reactivate_cmd,
    revoke_cmd,
    set_admin_cmd,
)
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository
from eyened_orm.utils.db_users import create_user
from eyened_orm.utils.factories import make_creator, make_project


def test_an_unknown_role_fails_at_the_boundary_naming_the_valid_ones():
    result = CliRunner().invoke(
        grant_cmd, ["--user", "alice", "--project", "A", "--role", "admin"]
    )
    assert result.exit_code == 2
    for name in ("read_only", "grader", "project_admin"):
        assert name in result.output


@pytest.fixture()
def stub_database(session, monkeypatch):
    """Hand the command the in-memory test session instead of a real Database().

    get_database() builds a live MySQL connection, which the SQLite suite has
    no way to provide; patching it is what makes the shell testable at all.
    """

    class _FakeDatabase:
        @contextmanager
        def get_session(self):
            try:
                yield session  # deliberately not closed: the test reads after
            finally:
                # Discard anything the command left uncommitted. Without this the
                # fixture hands back the same live session, so a shell that never
                # commits is indistinguishable from one that does.
                session.rollback()

    monkeypatch.setattr(rbac_module, "get_database", lambda: _FakeDatabase())


@pytest.fixture()
def alice(session, stub_database):
    creator = make_creator(session, "alice")
    session.commit()
    return creator


def test_declining_the_confirmation_aborts_and_grants_nothing(
    session, stub_database, spanning, alice
):
    """The prompt is the whole point of the plan/apply split: an administrator
    who answers 'n' must end with no membership at all."""
    result = CliRunner().invoke(
        grant_for_task_cmd,
        ["--user", "alice", "--task", str(spanning["task"]), "--role", "grader"],
        input="n\n",
    )
    assert result.exit_code == 1
    # click 8.4.2 catches click.Abort inside main()'s standalone mode and
    # re-raises as SystemExit(1), so result.exception is never click.Abort --
    # only the "Aborted!" text (printed exactly on that path) proves the
    # prompt itself was reached, rather than some earlier, unrelated failure
    # that also happens to exit 1 and grant nothing.
    assert "Aborted!" in result.output
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {}


def test_confirming_applies_every_project_the_tasks_touch(
    session, stub_database, spanning, alice
):
    """The accept path: confirming grants in every project the task spans, not
    just the first one the review block happened to print."""
    result = CliRunner().invoke(
        grant_for_task_cmd,
        ["--user", "alice", "--task", str(spanning["task"]), "--role", "grader"],
        input="y\n",
    )
    assert result.exit_code == 0
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {
        spanning["projects"]["A"]: ProjectRole.grader,
        spanning["projects"]["B"]: ProjectRole.grader,
    }


def test_yes_skips_the_prompt(session, stub_database, spanning, alice):
    """No input is supplied: a command that still prompted would abort, so this
    fails if --yes stops suppressing the confirmation."""
    result = CliRunner().invoke(
        grant_for_task_cmd,
        ["--user", "alice", "--task", str(spanning["task"]),
         "--role", "grader", "--yes"],
    )
    assert result.exit_code == 0
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {
        spanning["projects"]["A"]: ProjectRole.grader,
        spanning["projects"]["B"]: ProjectRole.grader,
    }


def test_grant_all_is_registered_on_the_eorm_group():
    """A command that is defined but never appended to rbac_commands is
    invisible to `eorm`, and every test that invokes it directly still passes."""
    from eyened_orm.cli import eorm

    assert "grant-all" in eorm.commands


def _memberships(session):
    return session.query(ProjectMember).count()


def _seed_grant_all(session):
    """A creator with a real password hash -- unlike the `alice` fixture above,
    whose `make_creator` leaves PasswordHash NULL, which `grant_all` would skip."""
    create_user(session, "alice", "pw")
    make_project(session, "A")
    make_project(session, "B")
    session.commit()


def test_yes_skips_the_confirmation_and_grants(session, stub_database):
    _seed_grant_all(session)

    result = CliRunner().invoke(grant_all_cmd, ["--yes"])
    assert result.exit_code == 0, result.output
    assert _memberships(session) == 2
    # Pins the counts *and their order*: this seed has 1 creator and 2
    # projects, so swapping the {creators}/{projects} interpolations in
    # grant_all_cmd's echo would misreport "2 creator(s) across 1
    # project(s)" instead of "1 creator(s) across 2 project(s)" -- a change
    # the exit-code and _memberships() assertions above would not catch.
    assert "2 membership(s) written for 1 creator(s) across 2 project(s)." in result.output


def test_declining_the_confirmation_writes_nothing(session, stub_database):
    """The confirmation is the only thing standing between a typo and 3,256
    memberships. Without this test it can be deleted and the suite stays green."""
    _seed_grant_all(session)

    result = CliRunner().invoke(grant_all_cmd, input="n\n")
    assert result.exit_code == 1
    # As in test_declining_the_confirmation_aborts_and_grants_nothing above:
    # exit_code == 1 and zero memberships are also satisfied by any
    # pre-prompt failure, so "Aborted!" is what proves the prompt itself was
    # reached rather than some unrelated early exit.
    assert "Aborted!" in result.output
    assert _memberships(session) == 0


def test_confirming_at_the_prompt_grants(session, stub_database):
    """Positive control: the decline test above must fail for the right reason."""
    _seed_grant_all(session)

    result = CliRunner().invoke(grant_all_cmd, input="y\n")
    assert result.exit_code == 0, result.output
    assert _memberships(session) == 2


def test_the_round_trip_persists_and_reports_each_outcome(session, stub_database, alice):
    """The shell commits (else the second invocation would see an active user
    again), and each command distinguishes a change it made from one it found
    already done."""
    first = CliRunner().invoke(deactivate_cmd, ["--user", "alice"])
    assert first.exit_code == 0
    assert "deactivated" in first.output
    assert alice.Inactive is True

    again = CliRunner().invoke(deactivate_cmd, ["--user", "alice"])
    assert again.exit_code == 0
    assert "already inactive" in again.output

    back = CliRunner().invoke(reactivate_cmd, ["--user", "alice"])
    assert back.exit_code == 0
    assert "reactivated" in back.output
    assert alice.Inactive is False


@pytest.mark.parametrize("command", (deactivate_cmd, reactivate_cmd))
def test_an_unknown_user_is_a_clean_error_not_a_traceback(session, stub_database, command):
    """ClickException exits 1 with its message on the stream; an unhandled
    LookupError exits 1 too, so the message is what separates them."""
    result = CliRunner().invoke(command, ["--user", "nosuchuser"])
    assert result.exit_code == 1
    assert "nosuchuser" in result.output
    assert "Traceback" not in result.output


def _init_admin(username: str, password: str):
    """Invoke ``eorm init-admin`` non-interactively.

    ``--password`` is passed explicitly on every call, including the empty
    string: the option declares ``envvar="EYENED_API_ADMIN_PASSWORD"``, so
    omitting it would let a value in the developer's own environment decide
    what these tests measure.
    """
    return CliRunner().invoke(
        init_admin, ["--username", username, "--password", password]
    )


def _init_admin_audit(session):
    return session.scalars(
        select(AuditLog)
        .where(AuditLog.TrustedPath == "eorm init-admin")
        .order_by(AuditLog.AuditLogID)
    ).all()


def test_init_admin_audits_a_creation_as_a_creation(session, stub_database):
    result = _init_admin("root", "s3cret")

    assert result.exit_code == 0, result.output
    assert "root: created" in result.output
    rows = _init_admin_audit(session)
    assert len(rows) == 1
    assert rows[0].Action == "INSERT"
    assert rows[0].Changes == {
        "username": "root",
        "is_admin": True,
        "outcome": "created",
    }


def test_init_admin_audits_a_promotion_as_a_promotion(session, stub_database):
    make_creator(session, "root")
    session.commit()

    result = _init_admin("root", "")

    assert result.exit_code == 0, result.output
    assert "root: promoted" in result.output
    rows = _init_admin_audit(session)
    assert len(rows) == 1
    assert rows[0].Action == "UPDATE"
    assert rows[0].Changes == {
        "username": "root",
        "is_admin": True,
        "outcome": "promoted",
    }


def test_init_admin_audits_a_password_reset_as_a_password_reset(session, stub_database):
    """The defect this pins: an already-administrator account given a new
    password produced an audit row identical to a real promotion -- asserting
    a privilege change that did not occur, while the credential rotation on
    the highest-privilege account in the system went unrecorded.

    ``is_admin`` must be *absent*, not False: the key's presence is what an
    auditor reconstructing administrator grants keys on.
    """
    ensure_admin(session, "root", "s3cret")
    session.commit()

    result = _init_admin("root", "rotated")

    assert result.exit_code == 0, result.output
    assert "root: password_reset" in result.output
    rows = _init_admin_audit(session)
    assert len(rows) == 1
    assert rows[0].Action == "UPDATE"
    assert rows[0].Changes == {
        "username": "root",
        "password_changed": True,
        "outcome": "password_reset",
    }
    # Never the secret itself, nor the hash.
    assert "rotated" not in str(rows[0].Changes)


def test_init_admin_audits_a_promotion_with_a_password_as_both(session, stub_database):
    make_creator(session, "root")
    session.commit()

    result = _init_admin("root", "s3cret")

    assert result.exit_code == 0, result.output
    assert "root: promoted_and_password_reset" in result.output
    rows = _init_admin_audit(session)
    assert len(rows) == 1
    assert rows[0].Action == "UPDATE"
    assert rows[0].Changes == {
        "username": "root",
        "is_admin": True,
        "password_changed": True,
        "outcome": "promoted_and_password_reset",
    }


def test_init_admin_writes_no_audit_row_when_nothing_changed(session, stub_database):
    """The control for the four above: a re-run that changes nothing must not
    add a row, or every assertion on `len(rows) == 1` above would be satisfied
    by a command that audits unconditionally."""
    ensure_admin(session, "root", "s3cret")
    session.commit()

    result = _init_admin("root", "s3cret")

    assert result.exit_code == 0, result.output
    assert "root: unchanged" in result.output
    assert _init_admin_audit(session) == []


def test_set_admin_round_trip_persists_and_reports_each_outcome(
    session, stub_database, alice
):
    """The shell commits (else the second invocation would see a non-admin
    again), and the command distinguishes a change it made from one it found
    already done. The --off leg is the point of the command: init-admin can
    already do --on."""
    on = CliRunner().invoke(set_admin_cmd, ["--user", "alice", "--on"])
    assert on.exit_code == 0, on.output
    assert "is now an administrator" in on.output
    assert alice.IsAdmin is True

    again = CliRunner().invoke(set_admin_cmd, ["--user", "alice", "--on"])
    assert again.exit_code == 0, again.output
    assert "already an administrator; no change" in again.output

    off = CliRunner().invoke(set_admin_cmd, ["--user", "alice", "--off"])
    assert off.exit_code == 0, off.output
    assert "is no longer an administrator" in off.output
    assert alice.IsAdmin is False


def test_set_admin_on_an_unknown_user_is_a_clean_error_not_a_traceback(
    session, stub_database
):
    """ClickException exits 1 with its message on the stream; an unhandled
    LookupError exits 1 too, so the message is what separates them."""
    result = CliRunner().invoke(set_admin_cmd, ["--user", "nosuchuser", "--off"])
    assert result.exit_code == 1
    assert "nosuchuser" in result.output


def test_revoke_all_removes_every_membership_and_names_each(
    session, stub_database, alice
):
    """The reset step of the developer loop. Naming each removal is the only
    read-back this phase ships, so the echo is part of the contract, not
    decoration."""
    make_project(session, "A")
    make_project(session, "B")
    grant(session, username="alice", project_name="A", role=ProjectRole.grader)
    grant(session, username="alice", project_name="B", role=ProjectRole.read_only)
    session.commit()

    result = CliRunner().invoke(revoke_cmd, ["--user", "alice", "--all", "--yes"])
    assert result.exit_code == 0, result.output
    assert "REVOKE grader in A" in result.output
    assert "REVOKE read_only in B" in result.output
    assert "alice: revoked from 2 project(s)" in result.output
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {}


@pytest.mark.parametrize(
    "args",
    (
        ["--user", "alice"],
        ["--user", "alice", "--project", "A", "--all"],
    ),
    ids=("neither", "both"),
)
def test_revoke_requires_exactly_one_of_project_and_all(session, stub_database, args):
    """Neither is a typo that would otherwise silently do nothing; both is a
    typo that would otherwise silently do everything. Click has no native
    construct for 'exactly one of', so this guard is hand-written and can be
    deleted without any other test noticing."""
    result = CliRunner().invoke(revoke_cmd, args)
    assert result.exit_code == 2
    assert "exactly one of --project or --all" in result.output
    assert "Traceback" not in result.output
