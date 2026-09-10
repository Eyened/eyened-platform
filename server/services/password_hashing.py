"""Bound how many Argon2 password hashes an API worker computes at once.

Argon2 is memory-hard on purpose: this deployment's parameters cost 64 MiB and
roughly 75ms per hash. While route handlers ran on the event loop, that cost was
serialized by accident -- a worker computed one hash at a time. Running handlers
in the threadpool removes that accident, and `/auth/login` and `/auth/token`
require no credentials to reach, so an anonymous caller would otherwise multiply
64 MiB by the threadpool limit.

The gate is a `threading` semaphore rather than an anyio one because its callers
are synchronous handlers running in Starlette's threadpool, not coroutines.

The trade it makes deliberately: a thread waiting here still occupies its
threadpool slot, and on the login path it is already holding a pooled
connection. Threads and connections are bounded resources whose exhaustion is
fast and visible -- pool_timeout fails a checkout in 5s. Exceeding memory kills
the worker instead, so memory is the one that gets the hard bound.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from server.config import settings

_gate = threading.BoundedSemaphore(settings.password_hash_concurrency)


@contextmanager
def password_hash_capacity() -> Iterator[None]:
    """Hold a hashing slot for the duration of the block."""
    with _gate:
        yield
