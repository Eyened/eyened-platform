"""`eorm initialize-database` runs the migration trail, not create_all().

create_all() here would put a fresh database's schema outside alembic's knowledge.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from eyened_orm import cli as cli_module
from eyened_orm.cli import initialize_database as initialize_database_cmd


@pytest.fixture()
def stub_database(monkeypatch):
    """Hand the command a stand-in Database and record the trail invocation."""
    calls = {}

    class _FakeDatabase:
        engine = object()
        database_settings = object()

    def fake_upgrade_to_head(engine):
        calls["engine"] = engine
        return "orm_baseline"

    monkeypatch.setattr(
        cli_module, "get_database", lambda confirmation=True: _FakeDatabase()
    )
    monkeypatch.setattr(
        "eyened_orm.utils.alembic_utils.upgrade_to_head", fake_upgrade_to_head
    )
    return calls


def test_initialize_database_runs_the_migration_trail(stub_database):
    """It calls upgrade_to_head and reports the resulting head revision."""
    result = CliRunner().invoke(initialize_database_cmd, [])

    assert result.exit_code == 0, result.output
    assert "orm_baseline" in result.output
    assert "engine" in stub_database
