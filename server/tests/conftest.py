from eyened_orm.utils.sqlite_testdb import (  # noqa: F401
    SessionLocal,
    engine,
    session,
)

import os


def pytest_configure(config):
    # Note: due to the way application configuration is created and imported throughout the application,
    # there is no clean way to test code that imports (database) settings, which is virtually everything.
    # Below is a rather ugly hack to work around this, that will probably result in new issues when we
    # want to add database-backend tests for the server. The correct solution is to handle settings
    # loading differently in the application.

    # Add mock values for required configuration values
    os.environ.setdefault("EYENED_DATABASE_USER", "test_user")
    os.environ.setdefault("EYENED_DATABASE_PASSWORD", "test_password")


import pytest
from contextlib import contextmanager
from fastapi.testclient import TestClient


class _SessionBoundDatabase:
    """Stand-in for eyened_orm.Database exposing get_session() bound to a
    fixed Session (the `session` fixture), rather than creating a fresh one
    per call: HTTP tests seed/verify data through the same Session object the
    request handler receives, and the `session` fixture (sqlite_testdb.py)
    already owns opening/closing it -- this stand-in must not close it.

    Monkeypatching server.db.database to this lets the client fixture drive
    the real, unmodified server.db.get_db (design §4: "match production at
    the fixture, not in production code") instead of a hand-copied
    re-implementation of its commit/rollback body.
    """

    def __init__(self, session) -> None:
        self._session = session

    @contextmanager
    def get_session(self):
        yield self._session


@pytest.fixture()
def client(session, monkeypatch):
    """TestClient bound to app_api, with the DB engine and auth dependency overridden.

    app_api is the sub-app mounted at /api in server.main, so paths here carry no
    /api prefix. Binding to it (rather than to `app`) also skips the lifespan and
    the Redis connection, which tests neither have nor need.
    """
    # Imported lazily: pytest_configure above must set the DB env vars first.
    import server.db as server_db
    from server.main import app_api
    from server.routes.auth import CurrentUser, get_current_user

    # Bind server.db.database to this test's session, so `Depends(get_db)` runs
    # the real, un-overridden server.db.get_db against it for every request.
    monkeypatch.setattr(server_db, "database", _SessionBoundDatabase(session))

    # A CurrentUser with no backing Creator row: search never calls get_creator(),
    # and seeding one would pollute /instances/search/signature's creator list.
    app_api.dependency_overrides[get_current_user] = lambda: CurrentUser(
        creator_id=1, username="tester", role="admin"
    )
    with TestClient(app_api) as c:
        yield c
    # Pop only what this fixture installed: app_api is a module-level singleton, so
    # clear() would silently delete overrides another fixture or test owns.
    app_api.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def signed_jwts(monkeypatch):
    """Give JWT issuance/verification a usable HMAC key.

    Default test settings leave Settings.secret_key empty, which HS256
    signing rejects; any auth test that hits a route issuing or verifying a
    JWT (login, refresh, oidc/authenticate, ...) needs this.
    """
    from server.config import Settings

    monkeypatch.setattr(
        Settings,
        "secret_key_value",
        property(lambda self: "test-secret-key-0123456789abcdef"),
    )
