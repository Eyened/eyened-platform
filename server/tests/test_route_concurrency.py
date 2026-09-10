"""A slow request must not block a fast one.

Every other guard in this change is structural -- it checks declarations,
configuration or source shape. This is the one test that exercises the
behaviour those changes exist to produce, and it is what covers the AST guard's
blind spot: the guard cannot see a synchronous service call left unwrapped
inside an async handler, but this test can.

Negative control: on the tree before the handler flip, this test fails.

No database is involved. The suite's client fixture binds a single Session for
the whole test, which two concurrent requests must not share, so the three
dependencies these two routes use are overridden and get_db is never reached.
"""
from __future__ import annotations

import time

import anyio
import httpxyz as httpx
import pytest

# Long enough for a wide margin on a loaded CI box, short enough not to slow
# the suite noticeably.
SLOW_SECONDS = 1.0
# Deliberately generous. The claim is "the fast request did not wait for the
# slow one", not a latency budget -- a tight threshold on shared CI buys
# flakiness and no extra signal.
FAST_BUDGET = SLOW_SECONDS / 2


class _SlowTaskService:
    """Stands in for TaskService, blocking its thread like a slow query."""

    def list_tasks(self, *, include_projects: bool = False):
        time.sleep(SLOW_SECONDS)
        return [], {}, None


class _FastFeatureService:
    """Stands in for FeatureService, returning immediately."""

    def list_features(self, with_counts: bool = False):
        return [], {}


@pytest.fixture()
def concurrency_app():
    from server.main import app_api
    from server.routes.auth import CurrentUser, get_current_user
    from server.services.feature_service import get_feature_service
    from server.services.task_service import get_task_service

    overrides = {
        get_task_service: lambda: _SlowTaskService(),
        get_feature_service: lambda: _FastFeatureService(),
        get_current_user: lambda: CurrentUser(creator_id=1, username="tester"),
    }
    app_api.dependency_overrides.update(overrides)
    yield app_api
    # Pop only what this fixture installed: app_api is a module-level singleton.
    for dep in overrides:
        app_api.dependency_overrides.pop(dep, None)


def test_a_slow_request_does_not_block_a_fast_one(concurrency_app):
    """GET /features completes while GET /task is still inside a blocking call."""
    results: dict[str, float] = {}

    async def scenario() -> None:
        started_at = time.perf_counter()
        transport = httpx.ASGITransport(app=concurrency_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as ac:

            async def slow() -> None:
                r = await ac.get("/task")
                results["slow_status"] = r.status_code

            async def fast() -> None:
                # Give the slow request time to reach its blocking call.
                await anyio.sleep(0.1)
                r = await ac.get("/features")
                results["fast_status"] = r.status_code
                # Measured from the scenario's start, not from just before the
                # request: if the loop is blocked, this coroutine does not even
                # get to run until the slow call returns, and a locally-started
                # timer would report a fast request that in fact waited.
                results["fast_done"] = time.perf_counter() - started_at

            async with anyio.create_task_group() as tg:
                tg.start_soon(slow)
                tg.start_soon(fast)

    anyio.run(scenario)

    assert results["slow_status"] == 200
    assert results["fast_status"] == 200
    assert results["fast_done"] < FAST_BUDGET, (
        f"the fast request finished {results['fast_done']:.2f}s after the slow one "
        f"started, so it waited on it: a route handler is blocking the event loop"
    )
