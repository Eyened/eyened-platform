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

from eyened_orm import ProjectMember
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.commands import rbac as rbac_module
from eyened_orm.commands.rbac import grant_all_cmd, grant_cmd, grant_for_task_cmd
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
            yield session  # deliberately not closed: the test reads after

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


def test_declining_the_confirmation_writes_nothing(session, stub_database):
    """The confirmation is the only thing standing between a typo and 3,256
    memberships. Without this test it can be deleted and the suite stays green."""
    _seed_grant_all(session)

    result = CliRunner().invoke(grant_all_cmd, input="n\n")
    assert result.exit_code == 1
    assert _memberships(session) == 0


def test_confirming_at_the_prompt_grants(session, stub_database):
    """Positive control: the decline test above must fail for the right reason."""
    _seed_grant_all(session)

    result = CliRunner().invoke(grant_all_cmd, input="y\n")
    assert result.exit_code == 0, result.output
    assert _memberships(session) == 2
