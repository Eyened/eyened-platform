# Performance

### Stop paying scoped segmentation counts on every app load
- **Status:** open
- **Source:** `feature/rbac-multi-project-tasks` final review, 2026-08-13
- **Problem:** `client/src/lib/data/globalContext.svelte.ts:46` calls `fetchFeatures({ with_counts: true })` in `GlobalContext.init()`, so every non-admin runs `FeatureRepository.segmentation_counts`, whose scope walks `Segmentation → ImageInstance → Series → Study → Patient`. Measured 2026-08-24 (2 GB pool): admin/unscoped 8 ms, all 44 projects ~260–300 ms, single projects unpredictable 1–758 ms; single-table proxy 22 ms. `ImageInstance` (1.9 GB) is most of it.
- **Fix:** first, drop `with_counts` from boot if counts are only shown in feature management. Else a short-TTL cache. Last resort: a denormalized, advisory-only `Segmentation.CachedProjectID` + index `(ProjectID, FeatureID)` (52,860 rows), kept in the write transaction, with a test that it equals the walked counts.
- **Note:** query rewrites and new indexes were measured and do not help; `Patient.ProjectID` must stay the sole project authority; `count_segmentations` stays unscoped on purpose (deletion guard).

### Check for oversized `IN` lists on `ImageInstance`
- **Status:** open
- **Source:** perf gate on `feature/tasks-page-performance`, 2026-08-20
- **Problem:** `WHERE ImageInstanceID IN (...)` with 14,014 ids (task 70's link count) makes MySQL 8.0.27 full-scan 1.86 M rows (~2.3 s); 2,000 ids still range-scans. Unknown whether any production path (large `selectin` loads, id-list repository methods) builds such a list.
- **Fix:** find any such path; chunk the list. Confirm the cause via warning 3170 (`range_optimizer_max_mem_size`, 8 MB default).

### Size the API pool for multi-hop connection checkout
- **Status:** open
- **Source:** PR #219 review, 2026-08-24
- **Problem:** `Settings._threads_cannot_outnumber_connections` (`server/config.py`) assumes one connection per thread, but a request holds its connection across several threadpool hops. Measured 20 connections for 16 threads; 31 of 64 concurrent `GET /api/task` returned 500 (pool timeout). `test_route_concurrency.py` overrides `get_db`, so CI cannot see it.
- **Fix:** one of: bound in-flight requests per worker; stop holding the connection in `get_access_scope`; size the pool for the measured checkout:thread ratio.

### Pick one eager-loading convention and drop dead loads
- **Status:** open
- **Source:** PR #145 review (@bjliefers), 2026-07-16
- **Problem:** some repositories bake in `selectinload` graphs (`FormAnnotationRepository.list_active`, `SegmentationRepository.get_with_tag_links`), others take flags. Form-annotation and segmentation GET/list load tag links but call the DTO converter with `with_tag_metadata=False`, so `tags` stays `[]`.
- **Fix:** one convention (explicit inputs to DTO converters rather than walking ORM relationships); remove the unused tag-link loads.
