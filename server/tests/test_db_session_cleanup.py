"""get_db returns its connection on the error path, not just the happy one.

A leak here used to be masked by a small, fast-recycling pool. With the tuned
pool it exhausts the worker's connections and surfaces as the pool_timeout
stall this change exists to remove -- so the failing path is pinned.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest


class _RecordingSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class _RecordingDatabase:
    """Mirrors eyened_orm.Database.get_session: closes in a finally block."""

    def __init__(self, session: _RecordingSession) -> None:
        self._session = session

    @contextmanager
    def get_session(self):
        try:
            yield self._session
        finally:
            self._session.close()


def _drive(monkeypatch, raise_in_handler: bool) -> _RecordingSession:
    import server.db as server_db

    recorded = _RecordingSession()
    monkeypatch.setattr(server_db, "database", _RecordingDatabase(recorded))

    gen = server_db.get_db()
    next(gen)
    if raise_in_handler:
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("handler blew up"))
    else:
        with pytest.raises(StopIteration):
            next(gen)
    return recorded


def test_successful_request_commits_and_closes(monkeypatch):
    """The happy path is the control: without it, the failing path proves less."""
    recorded = _drive(monkeypatch, raise_in_handler=False)
    assert recorded.committed
    assert not recorded.rolled_back
    assert recorded.closed


def test_failing_request_rolls_back_and_closes(monkeypatch):
    """A raising handler must not strand its connection outside the pool."""
    recorded = _drive(monkeypatch, raise_in_handler=True)
    assert not recorded.committed
    assert recorded.rolled_back
    assert recorded.closed
