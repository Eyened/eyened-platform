"""`eorm bootstrap`: which steps run for each database state.

Migrations are MySQL-only, so the alembic calls and the seeding are replaced
with recorders; the Creator and AuditLog rows are real, on the SQLite fixture.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from eyened_orm import AuditLog, Creator
from eyened_orm.authz.bootstrap import ensure_admin
from eyened_orm.commands import bootstrap as bootstrap_module
from eyened_orm.commands.bootstrap import bootstrap
from eyened_orm.utils.db_users import verify_password

HEAD = "head_rev"


@pytest.fixture()
def db(session, monkeypatch):
    """Stub the schema state; return (state, calls) for the test to set and read."""
    state = {"current": HEAD}
    calls: list[str] = []

    class _FakeDatabase:
        engine = None

        @contextmanager
        def get_session(self):
            try:
                yield session  # deliberately not closed: the test reads after
            finally:
                session.rollback()

    def fake_upgrade(_engine):
        calls.append("migrate")
        state["current"] = HEAD
        return HEAD

    def fake_seed(_session, *, update=False):
        calls.append("seed")

    monkeypatch.setattr(bootstrap_module, "get_database", lambda: _FakeDatabase())
    monkeypatch.setattr(bootstrap_module, "get_head_revision", lambda: HEAD)
    monkeypatch.setattr(
        bootstrap_module, "get_current_alembic_revision", lambda _engine: state["current"]
    )
    monkeypatch.setattr(bootstrap_module, "upgrade_to_head", fake_upgrade)
    monkeypatch.setattr(bootstrap_module, "seed_form_schemas", fake_seed)
    return state, calls


def _run(**env):
    unset = {
        "EYENED_AUTO_MIGRATE": None,
        "EYENED_API_ADMIN_USERNAME": None,
        "EYENED_API_ADMIN_PASSWORD": None,
    }
    return CliRunner().invoke(bootstrap, [], env={**unset, **env})


def _admin(session):
    return session.scalars(select(Creator).where(Creator.CreatorName == "admin")).one()


def _bootstrap_audit(session):
    return session.scalars(
        select(AuditLog).where(AuditLog.TrustedPath == "eorm bootstrap")
    ).all()


def test_an_empty_database_is_migrated_seeded_and_given_an_audited_admin(session, db):
    state, calls = db
    state["current"] = None

    result = _run(EYENED_API_ADMIN_PASSWORD="s3cret")

    assert result.exit_code == 0, result.output
    assert calls == ["migrate", "seed"]
    admin = _admin(session)
    assert admin.IsAdmin and not admin.Inactive
    assert verify_password("s3cret", admin.PasswordHash)
    [audit] = _bootstrap_audit(session)
    assert (audit.Action, audit.Changes) == (
        "INSERT",
        {"username": "admin", "is_admin": True, "outcome": "created"},
    )


def test_a_schema_behind_head_is_migrated_but_not_reseeded(session, db):
    state, calls = db
    state["current"] = "older_rev"
    ensure_admin(session, "admin", "pw")
    session.commit()

    result = _run()

    assert result.exit_code == 0, result.output
    assert calls == ["migrate"]


def test_an_opted_out_site_reports_pending_migrations_and_exits_zero(session, db):
    state, calls = db
    state["current"] = "older_rev"
    ensure_admin(session, "admin", "pw")
    session.commit()

    result = _run(EYENED_AUTO_MIGRATE="false")

    assert result.exit_code == 0, result.output
    assert calls == []
    assert "older_rev -> head_rev" in result.output


def test_a_first_admin_without_a_password_fails_naming_the_variable(session, db):
    result = _run()

    assert result.exit_code != 0
    assert "EYENED_API_ADMIN_PASSWORD" in result.output
    assert session.scalars(select(Creator)).all() == []


def test_a_bootstrapped_database_is_left_alone(session, db):
    """A password rotated after first boot survives: the admin step does not re-run."""
    _, calls = db
    ensure_admin(session, "admin", "rotated")
    session.commit()

    result = _run(EYENED_API_ADMIN_PASSWORD="initial")

    assert result.exit_code == 0, result.output
    assert calls == []
    assert verify_password("rotated", _admin(session).PasswordHash)
    assert _bootstrap_audit(session) == []
