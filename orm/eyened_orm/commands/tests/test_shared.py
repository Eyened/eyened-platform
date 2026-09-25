"""Tests for the state-based confirmation gate in get_database."""

from __future__ import annotations

import click
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from eyened_orm.commands import shared


class _FakeSettings:
    database = "eyened_database"
    host = "database"
    port = 3306


class _FakeDatabase:
    def __init__(self, engine):
        self.engine = engine
        self.database_settings = _FakeSettings()


@pytest.fixture
def empty_engine():
    """An engine whose database has no tables at all."""
    return create_engine("sqlite+pysqlite:///:memory:", future=True)


def _never_prompt(*_args, **_kwargs):
    raise AssertionError("get_database prompted when it should not have")


def test_empty_database_proceeds_without_prompting(monkeypatch, empty_engine, capsys):
    """A database with no tables is not gated, and the decision is logged loudly."""
    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(empty_engine))
    monkeypatch.setattr(shared.click, "prompt", _never_prompt)

    database = shared.get_database(confirmation=True)

    assert database.engine is empty_engine
    assert "no tables" in capsys.readouterr().out


def test_populated_database_still_demands_the_code(monkeypatch, engine):
    """A database with tables keeps the typed-code gate; a wrong code aborts."""
    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(engine))
    monkeypatch.setattr(shared.click, "prompt", lambda *a, **k: "WRONG")

    with pytest.raises(click.ClickException):
        shared.get_database(confirmation=True)


def test_populated_database_accepts_the_printed_code(monkeypatch, engine):
    """The gate still opens for an operator who types the code correctly."""
    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(engine))
    monkeypatch.setattr(shared.random, "choices", lambda *a, **k: list("ABCD"))
    monkeypatch.setattr(shared.click, "prompt", lambda *a, **k: "ABCD")

    assert shared.get_database(confirmation=True).engine is engine


def test_uninspectable_database_falls_back_to_prompting(monkeypatch, empty_engine, capsys):
    """An unreadable schema is not evidence of an empty one: fail safe, prompt."""

    def boom(_engine):
        raise SQLAlchemyError("access denied for user")

    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(empty_engine))
    monkeypatch.setattr(shared, "inspect", boom)
    monkeypatch.setattr(shared.click, "prompt", lambda *a, **k: "NOPE")

    with pytest.raises(click.ClickException):
        shared.get_database(confirmation=True)

    assert "Could not inspect the target database" in capsys.readouterr().out


def test_non_sqlalchemy_inspection_failure_also_falls_back_to_prompting(
    monkeypatch, empty_engine, capsys
):
    """The fail-safe is not scoped to SQLAlchemyError: any inspection failure
    (driver-level, programming error, whatever) must still fall back to
    prompting rather than propagating and crashing the command."""

    def boom(_engine):
        raise RuntimeError("driver segfaulted")

    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(empty_engine))
    monkeypatch.setattr(shared, "inspect", boom)
    monkeypatch.setattr(shared.click, "prompt", lambda *a, **k: "NOPE")

    with pytest.raises(click.ClickException):
        shared.get_database(confirmation=True)

    assert "Could not inspect the target database" in capsys.readouterr().out
