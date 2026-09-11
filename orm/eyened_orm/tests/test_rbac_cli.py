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

from eyened_orm import AuditLog, Creator, ProjectMember, TaskProject
from eyened_orm.authz.bootstrap import ensure_admin
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.commands import rbac as rbac_module
from eyened_orm.commands.rbac import (
    check_declarations,
    deactivate_cmd,
    grant_all_cmd,
    grant_cmd,
    grant_for_task_cmd,
    init_admin,
    reactivate_cmd,
    revoke_cmd,
    set_admin_cmd,
    set_password_cmd,
)
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository
from eyened_orm.utils.db_users import create_user, verify_password
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


def test_check_declarations_is_registered_on_the_eorm_group():
    """Same reason as grant-all: the query is tested in
    test_authz_administration.py and the shell can be invoked directly, so
    nothing else would notice it missing from rbac_commands."""
    from eyened_orm.cli import eorm

    assert "check-declarations" in eorm.commands


def test_check_declarations_reports_nothing_when_every_declaration_is_used(
    session, stub_database, spanning
):
    """The empty branch, against a fixture that does declare projects: every
    one of `spanning`'s declarations carries a link, so a shell that printed
    the declarations instead of the unused ones would not reach this line."""
    result = CliRunner().invoke(check_declarations, [])

    assert result.exit_code == 0
    assert result.output.strip() == "No unused declarations."


def test_check_declarations_names_the_task_and_the_project_of_an_unused_row(
    session, stub_database, spanning
):
    """The rows branch and its format. `a_only` holds links in A only, so
    declaring B gives it exactly one unused pair -- and an operator needs both
    ids to act on it, not a count."""
    session.add(
        TaskProject(TaskID=spanning["a_only"], ProjectID=spanning["projects"]["B"])
    )
    session.commit()

    result = CliRunner().invoke(check_declarations, [])

    assert result.exit_code == 0
    assert (
        f"task {spanning['a_only']}\tproject {spanning['projects']['B']}"
        in result.output
    )
    # The empty-case line and a row list are alternatives: printing both would
    # mean the shell never consulted the query it is shelling.
    assert "No unused declarations." not in result.output


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
    """ClickException exits 1 with its message on the stream and no traceback;
    AdminEntityNotFound is deliberately not a LookupError, so a stray KeyError
    or IndexError inside the call would surface as an unhandled exception with
    a traceback instead of this clean exit -- the traceback check is what
    separates them."""
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
    """ClickException exits 1 with its message on the stream and no traceback;
    AdminEntityNotFound is deliberately not a LookupError, so a stray KeyError
    or IndexError inside the call would surface as an unhandled exception with
    a traceback instead of this clean exit -- the traceback check is what
    separates them."""
    result = CliRunner().invoke(set_admin_cmd, ["--user", "nosuchuser", "--off"])
    assert result.exit_code == 1
    assert "nosuchuser" in result.output
    assert "Traceback" not in result.output


def test_grant_echoes_a_fresh_grant_without_a_previous_role(
    session, stub_database, alice
):
    """The fresh-grant echo, which carries no `(was ...)` because there was no
    previous role. Pinned as the whole line: a suffix that leaked onto this
    path -- `(was None)`, or the new role repeated -- would still contain the
    substring an `in result.output` check looks for, and the membership row
    below is identical either way."""
    project = make_project(session, "A")
    session.commit()

    result = CliRunner().invoke(
        grant_cmd, ["--user", "alice", "--project", "A", "--role", "grader"]
    )
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "alice: grader in A"
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {
        project.ProjectID: ProjectRole.grader
    }


def test_grant_that_changes_a_role_names_the_role_it_replaced(
    session, stub_database, alice
):
    """The `(was ...)` variant, in both directions. `previous` is the role that
    was *replaced*, so an echo that read it off the new grant instead would
    print `(was project_admin)` on the downgrade -- telling an administrator
    that the privilege they just removed is the one still held. Both legs also
    take the changed=True branch, so neither is distinguishable from the fresh
    grant above by exit code or by the row."""
    project = make_project(session, "A")
    session.commit()

    seed = CliRunner().invoke(
        grant_cmd, ["--user", "alice", "--project", "A", "--role", "read_only"]
    )
    assert seed.exit_code == 0, seed.output

    up = CliRunner().invoke(
        grant_cmd, ["--user", "alice", "--project", "A", "--role", "project_admin"]
    )
    assert up.exit_code == 0, up.output
    assert up.output.strip() == "alice: project_admin in A (was read_only)"

    down = CliRunner().invoke(
        grant_cmd, ["--user", "alice", "--project", "A", "--role", "grader"]
    )
    assert down.exit_code == 0, down.output
    assert down.output.strip() == "alice: grader in A (was project_admin)"
    # One membership throughout: a change replaces the role, it does not stack
    # a second row that `roles_for`'s dict would then hide behind one key.
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {
        project.ProjectID: ProjectRole.grader
    }
    assert _memberships(session) == 1


def test_granting_a_role_the_user_already_holds_reports_no_change(
    session, stub_database, alice
):
    """The idempotent branch. A re-grant that fell through to the changed=True
    echo would print `alice: grader in A` and leave the same row behind, so the
    text is the only thing that separates "did nothing" from "did it again"."""
    project = make_project(session, "A")
    session.commit()

    first = CliRunner().invoke(
        grant_cmd, ["--user", "alice", "--project", "A", "--role", "grader"]
    )
    assert first.exit_code == 0, first.output

    result = CliRunner().invoke(
        grant_cmd, ["--user", "alice", "--project", "A", "--role", "grader"]
    )
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "alice: already grader in A; no change"
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {
        project.ProjectID: ProjectRole.grader
    }


def test_revoke_removes_the_single_membership_and_echoes_it(
    session, stub_database, alice
):
    """The `--project` branch: `--all` already has three tests, but the rewrite
    that moved `--project` off `required=True` gave this path its own `if` and
    an early `return`, and nothing at the CLI level pinned it -- a dropped
    `session.commit()` or a fallthrough into the `--all` block would stay
    green.

    Alice also holds a membership in project B, which this invocation is never
    asked to touch. With only one membership, a missing `return` is invisible:
    `memberships_of` would find nothing left, the `--all` block would take its
    "holds no memberships; nothing to do" exit, and the already-printed
    "alice: revoked from A" would still satisfy the assertions below -- so a
    second, untouched membership is required to make that fallthrough loud.
    Do not shrink this back to a single project."""
    project_a = make_project(session, "A")
    project_b = make_project(session, "B")
    members = ProjectMemberRepository(session)
    members.upsert(alice.CreatorID, project_a.ProjectID, ProjectRole.grader)
    members.upsert(alice.CreatorID, project_b.ProjectID, ProjectRole.read_only)
    session.commit()

    result = CliRunner().invoke(
        revoke_cmd, ["--user", "alice", "--project", "A"]
    )
    assert result.exit_code == 0, result.output
    assert "alice: revoked from A" in result.output
    assert ProjectMemberRepository(session).roles_for(alice.CreatorID) == {
        project_b.ProjectID: ProjectRole.read_only
    }


def test_revoke_all_removes_every_membership_and_names_each(
    session, stub_database, alice
):
    """The reset step of the developer loop. Naming each removal is the only
    read-back this phase ships, so the echo is part of the contract, not
    decoration."""
    project_a = make_project(session, "A")
    project_b = make_project(session, "B")
    members = ProjectMemberRepository(session)
    members.upsert(alice.CreatorID, project_a.ProjectID, ProjectRole.grader)
    members.upsert(alice.CreatorID, project_b.ProjectID, ProjectRole.read_only)
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


def test_set_password_replaces_the_hash_so_only_the_new_password_verifies(
    session, stub_database
):
    """Both halves matter: asserting only that the new password verifies would
    also pass if the command appended a second credential instead of replacing
    the first."""
    create_user(session, "alice", "old-pw")
    session.commit()

    result = CliRunner().invoke(
        set_password_cmd, ["--user", "alice", "--password", "new-pw"]
    )
    assert result.exit_code == 0, result.output
    assert "alice: password set" in result.output

    stored = session.scalars(
        select(Creator).where(Creator.CreatorName == "alice")
    ).one()
    assert verify_password("new-pw", stored.PasswordHash) is True
    assert verify_password("old-pw", stored.PasswordHash) is False


def test_set_password_clears_the_legacy_hash_so_the_old_password_stops_working(
    session, stub_database
):
    """check_login (server/routes/auth.py) verifies PasswordHash first and
    falls through to the legacy `Password` column if that misses. If
    `set_password` left a pre-existing legacy hash in place, the password
    being reset away from would keep authenticating through that fallback --
    a "Forgot the password?" reset that doesn't actually revoke the old one.
    `create_user` never populates `Password`, so this seeds it directly rather
    than reusing the fixture above."""
    creator = make_creator(session, "alice")
    creator.PasswordHash = "existing-hash"
    creator.Password = b"\x00" * 32  # legacy pbkdf2 hash, still live
    session.commit()

    result = CliRunner().invoke(
        set_password_cmd, ["--user", "alice", "--password", "new-pw"]
    )
    assert result.exit_code == 0, result.output

    stored = session.scalars(
        select(Creator).where(Creator.CreatorName == "alice")
    ).one()
    assert stored.Password is None


def test_set_password_refuses_an_empty_password(session, stub_database):
    """`--password ""` is the only route to an empty value -- an empty entry at
    the interactive prompt makes Click re-prompt -- and it is exactly how the
    `_init_admin` helper above invokes its command, so it is a realistic
    invocation rather than a hypothetical one. Without this test the guard can
    be deleted and the suite stays green, leaving a login-disabling hash where
    a password was intended.
    """
    create_user(session, "alice", "old-pw")
    session.commit()

    result = CliRunner().invoke(set_password_cmd, ["--user", "alice", "--password", ""])
    assert result.exit_code == 2
    assert "password must not be empty" in result.output

    stored = session.scalars(
        select(Creator).where(Creator.CreatorName == "alice")
    ).one()
    assert verify_password("old-pw", stored.PasswordHash) is True


def test_the_deleted_administration_module_is_gone(session):
    """The whole point of the cutover: no importable path back to the
    Session-taking functions, so nothing can quietly keep using them."""
    import pytest as _pytest

    with _pytest.raises(ModuleNotFoundError):
        import eyened_orm.authz.administration  # noqa: F401


def test_revoke_all_rows_name_the_command_that_ran(session, stub_database, alice):
    """Behavior change 2. `apply_revoke_all` delegates to `revoke`, and the
    instance was built for `revoke`, so every row says `eorm revoke` rather
    than naming the inner call. The same property makes `grant-for-task` rows
    say `eorm grant-for-task` where they used to say `eorm grant`."""
    make_project(session, "A")
    make_project(session, "B")
    session.commit()

    for name in ("A", "B"):
        # Checked, not discarded: a grant that failed here would surface as a
        # confusing assertion about DELETE rows below instead of naming the
        # arrange that never happened.
        granted = CliRunner().invoke(
            grant_cmd, ["--user", "alice", "--project", name, "--role", "grader"]
        )
        assert granted.exit_code == 0, granted.output
    result = CliRunner().invoke(revoke_cmd, ["--user", "alice", "--all", "--yes"])
    assert result.exit_code == 0

    rows = session.scalars(
        select(AuditLog).where(AuditLog.Action == "DELETE")
    ).all()
    assert len(rows) == 2
    assert {r.TrustedPath for r in rows} == {"eorm revoke"}
