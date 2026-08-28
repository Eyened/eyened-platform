"""The three concurrency limits are interdependent, so they are validated.

An inconsistent triple does not misbehave loudly -- threads pile up in
pool.connect() and wait out the API's 5-second pool_timeout with no error
anywhere. Refusing to boot is the cheapest place to catch it.
"""
import pytest
from pydantic import ValidationError

from server.config import Settings, settings


def test_defaults_are_consistent():
    """The shipped defaults satisfy their own invariant."""
    s = Settings()
    assert s.threadpool_limit <= s.pool_size + s.max_overflow


def test_more_threads_than_connections_is_rejected():
    """A thread that cannot get a connection waits pool_timeout; refuse to boot."""
    with pytest.raises(ValidationError) as exc:
        Settings(pool_size=4, max_overflow=1, threadpool_limit=32)
    assert "exceeds pool capacity" in str(exc.value)


def test_threads_equal_to_capacity_is_accepted():
    """The boundary is allowed: every thread can hold a connection."""
    s = Settings(pool_size=8, max_overflow=2, threadpool_limit=10)
    assert s.threadpool_limit == 10


def test_api_engine_honours_the_configured_pool():
    """The tuned values must reach the API's engine, not merely validate in Settings.

    Settings validation and the ORM constructor are covered separately; the wiring
    between them was not, so server/db.py could stop passing them -- or pass
    constants -- with nothing failing.
    """
    from server.db import database

    pool = database.engine.pool
    assert pool.size() == settings.pool_size
    assert pool._max_overflow == settings.max_overflow
    assert pool._timeout == settings.pool_timeout
