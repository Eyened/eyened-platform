# Scoped segmentation counts walk four tables per request, and the boot path pays it

**Status:** open

## Source

RBAC multi-project enforcement work, branch `feature/rbac-multi-project-tasks`.
Surfaced by the final whole-branch review as the sole Important finding against
fix wave A, which scoped `FeatureRepository`'s segmentation counts to close a
cross-project information leak (any authenticated caller, including one with no
memberships, could read per-feature annotation volume for every project).

The scoping is correct and stays. This item is only about what it costs.

Measured on the shared dev MySQL 8.0.27 (`127.0.0.1:8983`) on 2026-08-13,
read-only `EXPLAIN` / `SELECT` only.

## What

`FeatureRepository.segmentation_counts` and `count_segmentations`
(`orm/eyened_orm/repositories/feature_repository.py`) count `Segmentation` rows
under the caller's scope. `Segmentation` carries no project of its own, so
`apply_scope` correlates the standard walk
`Segmentation → ImageInstance → Series → Study → Patient` and filters on
`Patient.ProjectID`.

Give `Segmentation` a denormalized `ProjectID` with a composite index on
`(ProjectID, FeatureID)`, reducing the read to a single-table grouped count.

`Segmentation` is **46,808 rows / 9 MB** — the backfill is trivial. (Contrast
`ImageInstance` at 1.85M rows / 1,637 MB; do not confuse the two.)

## Why

Measured, three warm runs each, against the top segmentation-holding project:

| query | time |
|---|---|
| `GROUP BY` alone (the administrator path — `apply_scope` returns the statement untouched) | **8 ms** |
| scoped, 1 project | **~600 ms** |
| scoped, 5 projects | ~630 ms |
| scoped, all 44 projects — **the post-cutover state** | **~600 ms** |
| single-table filtered `GROUP BY` (proxy for the denormalized shape) | **~10 ms** |

Two things make this worth an item rather than a shrug:

**The worst case is the normal case.** `eorm grant-all` gives every user
`grader` in all 44 projects at cutover, and that state measures the same ~600 ms.
Holding fewer projects does not help — the walk happens before the filter can
prune anything.

**It is on the boot path.** `client/src/lib/data/globalContext.svelte.ts:46`
calls `fetchFeatures({ with_counts: true })` inside `GlobalContext.init()`, so
this runs on **every application load for every non-administrator**.

**It is not live yet.** `ProjectMember` has 0 rows today, so every non-admin
resolves to an empty scope, which short-circuits at 0.2 ms. The regression
appears the moment `grant-all` runs. **That makes cutover the deadline.**

### Where the time goes

Adding one hop at a time, same 46,808 driving rows throughout:

| hop | table size | cumulative | increment |
|---|---|---|---|
| `Segmentation` `GROUP BY` | 9 MB | 8 ms | — |
| → `ImageInstance` (PK) | 1,637 MB | 300 ms | **+292 ms** |
| → `Series` (PK) | 419 MB | 465 ms | **+165 ms** |
| → `Study` (PK) | 39 MB | 535 ms | +70 ms |
| → `Patient` (PK) | 17 MB | 580 ms | +45 ms |
| → `ProjectID` filter | — | 600 ms | +20 ms |

Cost tracks **table size, not row count** — the same finding as
[the task→project map item](2026-08-07-task-project-materialized-map.md), and
for the same reason: `innodb_buffer_pool_size` is still **128 MB** against a
1,637 MB `ImageInstance`, so these are physical reads. That table has grown from
909 MB to 1,637 MB since 2026-08-07, so this constant is getting worse on its
own.

Unlike that item, this one is **not** a growth-class problem. The cost is linear
in `Segmentation` (46k rows, growing with annotation activity), not in
`SubTaskImageLink`. It is a constant-factor problem — which is precisely why a
constant-factor fix is the right answer here and was the wrong answer there.

## Design constraints

**This column must be advisory-only, and that must be written down where
somebody will read it.** The sibling item's rule — "a stale map is a security bug
in both directions" — applies to it because it governs *visibility*. This column
would govern only an aggregate **count**, so a stale value yields a wrong number,
not a wrong access decision.

That distinction is the whole risk. A `Segmentation.ProjectID` column sitting in
the schema is an obvious thing for a future reader to reuse in a scope predicate,
and at that moment staleness silently becomes an authorization bug. If this is
built:

- Name it so it cannot be mistaken for authority (`CachedProjectID`, or similar),
  and document on the column and in `orm/README.md` that
  `Patient.ProjectID` remains the sole project authority.
- Keep `apply_scope`'s graph walk as the **definition of truth**, exactly as the
  task→project item requires, and add a test asserting the denormalized counts
  equal the walked counts on a seeded dataset.
- Maintain it in the same transaction as `Segmentation` writes; `image_id` is
  already resolved through a scoped lookup on the create path, so the project is
  known there.
- **Patient project reassignment invalidates rows transitively** and does not go
  through the segmentation service. Same trap as the sibling item. Handle it
  explicitly or accept a documented staleness window on a count.

Needs a backfill migration, generated via `revision --autogenerate` and then
reviewed — never hand-written. `orm/README.md` is the authority for ORM columns
and migrations.

## Rejected alternatives, with evidence

- **Rewriting the query shape.** Measured all three forms against the same data:
  correlated `EXISTS` (current) ~700 ms, straight `INNER JOIN` ~690 ms, `IN`
  subquery on reachable image ids ~670 ms. MySQL normalizes them to the same
  plan. The review's suggested follow-up — "computing counts from an
  already-scoped subquery of feature ids" — is a **dead end**, and so is any
  other reordering. Join order in the SQL text is not a lever, the same
  conclusion the task→project item reached independently.
- **Adding an index.** There is nothing to add. `EXPLAIN` shows the plan already
  drives from `Segmentation` via `ix_Segmentation_Feature_Inactive` (42,564 rows)
  and then does `eq_ref` **primary-key** lookups, 1 row each, on all four
  parents. Every join column is indexed; there is no scan and no temporary table.
- **The review's stated diagnosis** — that the optimizer "abandons the covering
  index scan and drives the semi-join from `Patient`" — does not hold for the
  JOIN form, which drives from `Segmentation` and is equally slow. The direction
  of the walk was never the problem; the four pointer-chases per row are.

## Cheaper mitigations, if the deadline arrives first

- **Short-TTL cache on the counts.** They are advisory display data. No schema
  change, no staleness-becomes-security risk, ~20 lines. Weakest option on
  correctness of the number, strongest on risk.
- **Stop fetching counts at boot.** If the counts are only rendered in a feature
  management screen, `GlobalContext.init()` should not be asking for them at all.
  This is client work (out of scope for the RBAC branch, spec §12.4) and would
  make the whole item moot for the boot path. **Check this first — it may be
  free.**

## Separate, do regardless

`innodb_buffer_pool_size` is 128 MB, MySQL's untouched default, against a
now-5 GB+ database. This is already filed under the task→project item; it is
repeated here only because it is the direct cause of the per-hop numbers above
and it helps every query in the system. It does **not** substitute for this fix
(8 ms → 10 ms is already index-resident; the walk is the cost).

⚠️ Changing it restarts a container shared with other users' workloads on this
host; coordinate before doing it.
