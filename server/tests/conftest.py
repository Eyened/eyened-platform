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
from fastapi.testclient import TestClient


@pytest.fixture()
def client(session):
    """TestClient bound to app_api, with the DB and auth dependencies overridden.

    app_api is the sub-app mounted at /api in server.main, so paths here carry no
    /api prefix. Binding to it (rather than to `app`) also skips the lifespan and
    the Redis connection, which tests neither have nor need.
    """
    # Imported lazily: pytest_configure above must set the DB env vars first.
    from server.db import get_db
    from server.main import app_api
    from server.routes.auth import CurrentUser, get_current_user

    def _get_db():
        # Mirror production get_db so HTTP tests exercise the real commit/rollback
        # boundary once services stop committing (design §4).
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    # A CurrentUser with no backing Creator row: search never calls get_creator(),
    # and seeding one would pollute /instances/search/signature's creator list.
    app_api.dependency_overrides[get_db] = _get_db
    app_api.dependency_overrides[get_current_user] = lambda: CurrentUser(
        creator_id=1, username="tester", role="admin"
    )
    with TestClient(app_api) as c:
        yield c
    # Pop only what this fixture installed: app_api is a module-level singleton, so
    # clear() would silently delete overrides another fixture or test owns.
    app_api.dependency_overrides.pop(get_db, None)
    app_api.dependency_overrides.pop(get_current_user, None)
