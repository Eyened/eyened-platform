"""The `eorm create-user` shell.

Its own file rather than a block in test_rbac_cli.py because the fixture has to
patch a different module: create-user lives in cli.py, not commands/rbac.py, so
it resolves get_database through eyened_orm.cli. Two same-named fixtures
patching different targets in one file is a trap.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from click.testing import CliRunner

from eyened_orm import cli as cli_module
from eyened_orm.cli import create_user as create_user_cmd
from eyened_orm.utils.db_users import create_user


@pytest.fixture()
def stub_cli_database(session, monkeypatch):
    """Hand the command the in-memory test session instead of a real Database()."""

    class _FakeDatabase:
        @contextmanager
        def get_session(self):
            try:
                yield session  # deliberately not closed: the test reads after
            finally:
                session.rollback()

    monkeypatch.setattr(cli_module, "get_database", lambda: _FakeDatabase())


def test_a_duplicate_username_exits_non_zero(session, stub_cli_database):
    """It used to print the error and exit 0, so a setup script that minted
    nothing reported success. The exit code is the assertion that matters --
    the message was already correct."""
    create_user(session, "alice", "pw")
    session.commit()

    result = CliRunner().invoke(
        create_user_cmd, ["--username", "alice", "--password", "pw"]
    )
    assert result.exit_code == 1
    assert "Username already exists" in result.output
    assert "Traceback" not in result.output
