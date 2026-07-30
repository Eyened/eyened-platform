"""The bootstrap CLI's wiring: prompt -> ensure_admin -> commit.

``get_database`` is replaced with a stand-in yielding the test's SQLite session,
mirroring server/tests/conftest.py's ``_SessionBoundDatabase``: the point is to
exercise the real command body, not a re-implementation of it.
"""
from contextlib import contextmanager

from click.testing import CliRunner

from eyened_orm import Creator, is_system_admin
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401


class _SessionBoundDatabase:
    def __init__(self, session) -> None:
        self._session = session

    @contextmanager
    def get_session(self):
        yield self._session


def test_init_admin_creates_and_commits_a_system_admin(session, monkeypatch):
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))

    result = CliRunner().invoke(
        cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\n"
    )

    assert result.exit_code == 0, result.output
    admin = session.query(Creator).filter_by(CreatorName="admin").one()
    assert is_system_admin(admin) is True

    # Committed, not merely flushed -- the CLI is the transaction owner, so a
    # rollback afterwards must not take the admin with it. `in_transaction()` would
    # not prove this: the query above already opened a fresh transaction.
    session.rollback()
    assert session.query(Creator).filter_by(CreatorName="admin").count() == 1


def test_init_admin_is_idempotent(session, monkeypatch):
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))

    runner = CliRunner()
    runner.invoke(cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\n")
    result = runner.invoke(cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\n")

    assert result.exit_code == 0, result.output
    assert session.query(Creator).filter_by(CreatorName="admin").count() == 1
