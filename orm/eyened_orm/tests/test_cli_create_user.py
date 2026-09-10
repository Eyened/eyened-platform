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


def test_creating_a_user_writes_an_audit_row(session, stub_cli_database):
    """It used to write none -- the only account-creating path with no
    attribution at all, in a command set whose stated contract is that every
    state change is attributed. `auth:register` already writes the equivalent
    row for the HTTP path."""
    from sqlalchemy import select

    from eyened_orm import AuditLog

    result = CliRunner().invoke(
        create_user_cmd, ["--username", "bob", "--password", "pw"]
    )
    assert result.exit_code == 0

    row = session.scalars(select(AuditLog)).one()
    assert row.TrustedPath == "eorm create-user"
    assert row.ActorID is None
    assert row.Action == "INSERT"
    assert row.Entity == "Creator"
    assert row.Changes["username"] == "bob"


def test_a_rejected_duplicate_writes_no_audit_row(session, stub_cli_database):
    """The row records a creation, so a command that created nothing must not
    write one."""
    from sqlalchemy import select

    from eyened_orm import AuditLog

    create_user(session, "alice", "pw")
    session.commit()

    CliRunner().invoke(create_user_cmd, ["--username", "alice", "--password", "pw"])
    assert session.scalars(select(AuditLog)).all() == []
