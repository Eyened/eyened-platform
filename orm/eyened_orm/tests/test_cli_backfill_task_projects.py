"""The backfill CLI's wiring: plan -> report -> confirm -> commit.

``get_database`` is replaced with a stand-in yielding the test's SQLite session,
mirroring test_cli_init_admin.py: the point is to exercise the real command body.

``plan_backfill`` is substituted too, and that is not over-mocking -- it is how
the command gets an input at all. No test can seed a NULL ``Task.ProjectID``
(the model says NOT NULL and ``create_all`` builds the test schema from it), so
the real planner always returns an empty plan here and the command would exit at
"nothing to do" before reaching any branch worth testing. The rule itself is
pinned separately, on the pure ``classify``. Everything past the substitution is
the real command body writing to a real database.
"""
from contextlib import contextmanager

from click.testing import CliRunner
from sqlalchemy import select

from eyened_orm import Project
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401
from eyened_orm.utils.task_projects import BackfillPlan

SENTINEL = "_unresolved_legacy_tasks"   # the command's own --sentinel-name default


class _SessionBoundDatabase:
    def __init__(self, session) -> None:
        self._session = session

    @contextmanager
    def get_session(self):
        yield self._session


def _wire(monkeypatch, session, cli) -> None:
    """Point the command at this session, with a plan that parks one task."""
    monkeypatch.setattr(
        cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session)
    )
    monkeypatch.setattr(
        "eyened_orm.utils.task_projects.plan_backfill",
        lambda _session: BackfillPlan(anchored={}, to_park=[1]),
    )


def _sentinel(session):
    return session.scalar(select(Project).where(Project.ProjectName == SENTINEL))


def test_backfill_cli_dry_run_writes_nothing(session, monkeypatch):
    """--dry-run reports and returns before the sentinel is minted."""
    import eyened_orm.cli as cli

    _wire(monkeypatch, session, cli)

    result = CliRunner().invoke(cli.eorm, ["backfill-task-projects", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "nothing written" in result.output
    session.rollback()
    assert _sentinel(session) is None


def test_backfill_cli_confirmed_run_commits(session, monkeypatch):
    """The CLI owns the transaction, so its write must survive a later rollback."""
    import eyened_orm.cli as cli

    _wire(monkeypatch, session, cli)

    result = CliRunner().invoke(cli.eorm, ["backfill-task-projects"], input="y\n")

    assert result.exit_code == 0, result.output
    # Committed, not merely flushed. `in_transaction()` would not prove this --
    # the query below opens a fresh transaction either way.
    session.rollback()
    assert _sentinel(session) is not None
