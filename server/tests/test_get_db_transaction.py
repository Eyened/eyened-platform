from contextlib import contextmanager

import pytest

from eyened_orm import Feature

import server.db as server_db
from server.db import get_db


class _EngineBoundDatabase:
    """Stand-in for eyened_orm.Database exposing get_session() bound to the
    test engine's sessionmaker: a fresh Session per call, closed on exit --
    mirrors eyened_orm.Database.get_session (orm/eyened_orm/db.py) so the real
    server.db.get_db (imported above, unmodified) can be driven against the
    in-memory test engine instead of a hand-copied re-implementation of its
    body.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    @contextmanager
    def get_session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()


@pytest.fixture()
def bound_get_db(monkeypatch, SessionLocal):
    """Bind server.db.database to the test engine, then return the real get_db."""
    monkeypatch.setattr(server_db, "database", _EngineBoundDatabase(SessionLocal))
    return get_db


def _drain(gen):
    """Advance a get_db-style generator past its post-yield finalization."""
    try:
        next(gen)
    except StopIteration:
        pass


def test_get_db_commits_on_clean_exit(bound_get_db, SessionLocal):
    """The real get_db commits a clean-exit generator's pending write."""
    gen = bound_get_db()
    s = next(gen)
    s.add(Feature(FeatureName="committed"))
    _drain(gen)

    with SessionLocal() as verify:
        assert verify.query(Feature).filter_by(FeatureName="committed").count() == 1


def test_get_db_rolls_back_and_reraises_on_exception(bound_get_db, SessionLocal):
    """The real get_db calls session.rollback() (not just Session.close()'s
    implicit reset) before re-raising an exception thrown into the generator."""
    gen = bound_get_db()
    s = next(gen)
    s.add(Feature(FeatureName="doomed"))

    rollback_calls = []
    original_rollback = s.rollback

    def _tracking_rollback():
        rollback_calls.append(1)
        return original_rollback()

    s.rollback = _tracking_rollback

    with pytest.raises(ValueError):
        gen.throw(ValueError("boom"))

    # Discriminates get_db's explicit rollback from Session.close()'s implicit
    # connection-reset-on-checkin: Database.get_session()'s `finally:
    # session.close()` runs unconditionally (even if get_db's own `except:
    # session.rollback()` were deleted), and closing an in-transaction Session
    # rolls its connection back at the pool level regardless. A bare
    # `count() == 0` check on the row below holds either way -- it does NOT
    # discriminate get_db's own rollback call, which is why this test also
    # tracks the call directly.
    assert rollback_calls == [1]

    with SessionLocal() as verify:
        assert verify.query(Feature).filter_by(FeatureName="doomed").count() == 0
