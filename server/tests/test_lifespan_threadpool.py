"""The lifespan actually applies the configured threadpool limit.

Nothing else in the suite boots `app` -- every fixture binds `app_api` and skips
its lifespan -- so without this test the one line that sets the worker's thread
capacity is unverified by CI, and deleting it would go unnoticed.

anyio's own default is 40 and the configured limit is 16, so asserting the
configured value genuinely discriminates: if the line were missing, or ran
outside the event loop, 40 would still be in place.

The limiter is per-event-loop, not process-global (verified: setting it inside
one anyio.run does not affect the next), so this test cannot leak into others.
"""
from __future__ import annotations

import anyio
import anyio.to_thread

from server.config import settings
from server.main import app, lifespan


def test_lifespan_applies_the_configured_threadpool_limit():
    """anyio's default must be replaced by settings.threadpool_limit."""

    async def run() -> tuple[int, int]:
        before = anyio.to_thread.current_default_thread_limiter().total_tokens
        async with lifespan(app):
            after = anyio.to_thread.current_default_thread_limiter().total_tokens
        return before, after

    before, after = anyio.run(run)
    assert after == settings.threadpool_limit, (
        f"lifespan left the thread limiter at {before}; it must set "
        f"{settings.threadpool_limit}. anyio's default is 40, so an unchanged "
        "limiter means the line in lifespan is missing or ran outside the loop."
    )
