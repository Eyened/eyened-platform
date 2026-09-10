# API pool sizing assumes one connection per thread; a request takes several

**Status:** open

## Source

Whole-branch review of `feature/api-layer-concurrency` (PR #219) — the same
review as [the zarr write lock item](2026-08-24-zarr-storage-write-lock.md).

## What

`Settings._threads_cannot_outnumber_connections` in `server/config.py` enforces
`threadpool_limit <= pool_size + max_overflow`, which assumes one connection per
thread. FastAPI acquires a separate threadpool token per sync dependency, per
sync generator `__enter__`, for the endpoint, and again for response-model
validation, so one request holds its connection across several hops — including
while it queues for its next token holding no thread at all. The relation is
necessary, not sufficient.

Options considered on the branch and deliberately not taken:

- **Bound in-flight requests per worker** rather than threads, so the limit sits
  on the thing that actually holds a connection.
- **Stop taking the connection in `get_access_scope`** (`server/services/access_scope.py`),
  so it is not held across the endpoint's own hop.
- **Size the pool for the observed checkout-to-thread ratio** instead of 1:1.

## Why

Measured on this branch: **20 connections checked out against 16 threads**, and
at 64 concurrent clients on `GET /api/task`, **31 requests returned HTTP 500**
from pool-checkout timeout. The shipped `pool_timeout=5` bounds the symptom to a
fast, visible error instead of a 30-second hang; it does not fix the sizing.

CI cannot see any of this. `server/tests/test_route_concurrency.py` overrides
`get_db` away, so the pool is untested by construction — the next regression
here surfaces under load, not in the suite.
