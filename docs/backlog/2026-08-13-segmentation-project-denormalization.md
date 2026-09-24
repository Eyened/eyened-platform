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
read-only `EXPLAIN` / `SELECT` only; re-measured the same way on 2026-08-24.

## What

`FeatureRepository.segmentation_counts`
(`orm/eyened_orm/repositories/feature_repository.py:49`) counts `Segmentation`
rows under the caller's scope. `Segmentation` carries no project of its own, so
`apply_scope` correlates the standard walk
`Segmentation → ImageInstance → Series → Study → Patient` and filters on
`Patient.ProjectID`.

Its sibling `count_segmentations` (`:70`) is **not** in scope for this item. It is
deliberately unscoped, with a docstring saying why: it is a referential-integrity
guard for deletion, and scoping it turns a correct 409 into an uninformative 500.

Give `Segmentation` a denormalized `ProjectID` with a composite index on
`(ProjectID, FeatureID)`, reducing the read to a single-table grouped count.

`Segmentation` is **52,860 rows / 13 MB** — the backfill is trivial. (Contrast
`ImageInstance` at 1.7M rows / 1,932 MB; do not confuse the two.)

## Why

Re-measured 2026-08-24 under the 2 GB buffer pool, three warm runs each, against
the top segmentation-holding project:

| query | time |
|---|---|
| `GROUP BY` alone (the administrator path — `apply_scope` returns the statement untouched) | **8 ms** |
| scoped, 1 project | **28–758 ms**, see below |
| scoped, 5 projects | ~270–310 ms |
| scoped, all 44 projects — **what every user actually holds** | **~260–300 ms** |
| single-table filtered `GROUP BY` (proxy for the denormalized shape) | **22 ms** |

Three things make this worth an item rather than a shrug:

**It is live, on every application load.** This is the correction that matters:
`ProjectMember` now holds **1,364 rows — 31 creators, each a member of all 44
projects — and no `Creator` has `IsAdmin=1` at all**. So every one of them takes
the scoped path on every request; none short-circuits, and none is exempt. The
cutover this item was written to get ahead of has already happened.

**It is on the boot path.** `client/src/lib/data/globalContext.svelte.ts:46`
calls `fetchFeatures({ with_counts: true })` inside `GlobalContext.init()`, so
this runs on **every application load for every non-administrator** — which, per
the above, is everyone.

**Holding fewer projects is not a mitigation, and can be worse.** At 128 MB every
scope measured ~600 ms. At 2 GB the optimizer flips between two plans: for a
project with a small patient subtree it drives down from `Patient` (28 ms for a
46-segmentation project), and otherwise it drives up from `Segmentation` through
50,858 rows. Measured across single projects: 1 ms, 28 ms, 256 ms, 514 ms, **758
ms** — the 758 ms case is a single project costing *more* than holding all 44.
The number is unpredictable per scope, which is a worse property than being
uniformly slow.

### Where the time goes

Adding one hop at a time, same 52,860 driving rows throughout:

| hop | table size | cumulative | increment |
|---|---|---|---|
| `Segmentation` `GROUP BY` | 13 MB | 8 ms | — |
| → `ImageInstance` (PK) | 1,932 MB | 145 ms | **+137 ms** |
| → `Series` (PK) | 419 MB | 170 ms | +25 ms |
| → `Study` (PK) | 39 MB | 215 ms | +45 ms |
| → `Patient` (PK) | 17 MB | 250 ms | +35 ms |
| → `ProjectID` filter | — | 257 ms | +7 ms |

Cost tracks **table size, not row count** — the same finding as
[the task→project map item](2026-08-07-task-project-materialized-map.md), and
for the same reason: `ImageInstance` is 1,932 MB against a 2 GB pool, so it is
the one hop that still cannot stay resident and it still owns most of the cost.
It has grown 909 MB → 1,637 MB → 1,932 MB since 2026-08-07, so this constant
gets worse on its own; the pool increase bought headroom, not a fix.

Unlike that item, this one is **not** a growth-class problem. The cost is linear
in `Segmentation` (53k rows, growing with annotation activity), not in
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

Measured 2026-08-13 under the old 128 MB buffer pool; the absolute figures are of
that day, the conclusions do not depend on them.

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

## Do this first

- **Stop fetching counts at boot.** If the counts are only rendered in a feature
  management screen, `GlobalContext.init()` should not be asking for them at all.
  The fix is one client-side call site,
  `client/src/lib/data/globalContext.svelte.ts:46` — no schema change, no
  migration, no backfill — and it makes the whole item moot for the boot path.
  The cost is live today, so this is the recommended first action, not a
  fallback.

## Cheaper mitigations, if that is not available

- **Short-TTL cache on the counts.** They are advisory display data. No schema
  change, no staleness-becomes-security risk, ~20 lines. Weakest option on
  correctness of the number, strongest on risk.

## Separate, do regardless — DONE

The buffer pool is off MySQL's 128 MB default: `c9fcb56f` (2026-08-18) set
`--innodb-buffer-pool-size=${EYENED_DATABASE_BUFFER_POOL_SIZE:-2G}` in
`database/docker-compose.yaml`. It roughly halved the scoped walk and did **not**
substitute for this fix — the walk is still the cost.
