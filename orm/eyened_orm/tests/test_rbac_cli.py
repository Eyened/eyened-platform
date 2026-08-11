"""The CLI shell: tests for the things the shell adds over the functions.

Everything else is tested in test_authz_administration.py, which does not need
a real Database(). The accept path is not retested here: parse_role's happy
path is pinned there, and a CLI-level version of it could only assert that an
error string is *absent* from the output -- which is equally true of any
unrelated failure, so it would pass whether or not the parse ran.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from click.testing import CliRunner

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.commands import rbac as rbac_module
from eyened_orm.commands.rbac import grant_cmd, grant_for_task_cmd
from eyened_orm.repositories.project_member_repository import ProjectMemberRepository
from eyened_orm.utils.factories import make_creator


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
