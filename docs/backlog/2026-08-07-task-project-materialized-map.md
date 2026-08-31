# Task→project map: materialize it, or task listings degrade linearly with image links

**Status:** open

## Source

RBAC multi-project enforcement work, branch `feature/rbac-multi-project-tasks`,
during the task that scopes `Task` and `SubTask` reads (the containment rule at
the API). The plan it came from is a working document that is not tracked in
this repository, so it is named here rather than linked.

Measured on the shared dev MySQL 8.0.27 (`eyened-gpu:8983`) on 2026-08-07, with
read-only `EXPLAIN ANALYZE` / `SELECT` only; row counts, table sizes and timings
re-measured the same way on 2026-08-24. The plan's Task 12 block originally
mandated two covering indexes as the fix; that mandate was removed after this
analysis, and the block now points here.

## What

`_set_valued_predicate` in `orm/eyened_orm/authz/scoping.py` expresses task
containment as `NOT EXISTS (a project of this task outside the accessible set)`,
walking `SubTask → SubTaskImageLink → ImageInstance → Series → Study → Patient`.

Replace that per-request walk with a materialized `TaskProject(TaskID, ProjectID)`
table, reducing the read-path predicate to:

```sql
NOT EXISTS (SELECT 1 FROM TaskProject tp
            WHERE tp.TaskID = t.TaskID AND tp.ProjectID NOT IN (:accessible))
```

The map is **108 rows** today (2026-08-24). It grows with tasks × projects-per-task,
not with images — but note it was 43 rows on 2026-08-07, so it has grown 2.5× in
17 days. "Small and slow-growing" is half of this item's argument; re-check the
count rather than inheriting it.

## Why

Once task reads are scoped, the predicate costs **O(total `SubTaskImageLink`
rows) per request** for every non-administrator, independent of how many tasks
the caller can see and of `LIMIT`. (An administrator pays nothing: `apply_scope`
returns the statement untouched. Everyone else pays it now — when this was written
no repository applied the predicate, but `TaskRepository.list_all`
(`orm/eyened_orm/repositories/task_repository.py:86`) does, so the task listing is
a live cost. The figures below are still the predicate run by hand, not a timed
endpoint.) MySQL decorrelates the `NOT EXISTS`, dropping the `sib.TaskID = t.TaskID`
correlation, so it computes the task→project map for *every* task, materializes it
with deduplication, and then antijoins. The antijoin itself is free
(`Single-row index lookup on <subquery2>`, 0.000 ms/row); the whole cost is the one
materialization. That is why the figure is the same whether the outer table is
`Task` (48 rows) or `SubTask` (21,207), and why `LIMIT 50` does not help.

Re-measured 2026-08-24, three warm runs, under the 2 GB buffer pool: **311 / 315 /
317 ms**. (It was 1,640 / 1,672 / 1,653 ms on 2026-08-07 under MySQL's 128 MB
default — see "Separate" below; that is the whole difference.) Per-hop increments,
all driving the same 87,454 loops, table sizes as data+index:

| hop | table size | increment |
|---|---|---|
| `SubTask` → `SubTaskImageLink` | 11 MB | 44 ms |
| → `ImageInstance` (PK) | 1,932 MB | **+150 ms** |
| → `Series` (PK) | 419 MB | **+85 ms** |
| → `Study` (PK) | 39 MB | ~0 ms |
| → `Patient` (PK) | 17 MB | +30 ms |

Cost still tracks **table size, not row count** — `Study` does the same 87,454
clustered lookups over 210k rows and is now free, because at 39 MB it is resident.
The variable is whether the table fits in cache, which is why the one table that
does not fit still dominates.

**The growth argument is the reason this is worth doing**, and it is now stronger,
because half the constant-factor budget has already been spent. The buffer pool was
predicted to buy 5–8×; it bought 5.3× and is done. Covering indexes are the only
constant-factor lever left, worth an estimated 4–5×. The cost is linear in
`SubTaskImageLink`, so one order of magnitude of data growth consumes what remains:

| `SubTaskImageLink` rows | today (2 GB pool) | with covering indexes too (est.) |
|---|---|---|
| 87k (now) | 0.31 s | ~0.07 s |
| 870k (10×) | ~3.1 s | ~0.7 s |
| 8.7M (100×) | ~31 s | ~7 s |

A materialized map changes the complexity class instead of the constant, and stays
sub-millisecond at every row count above.

## Design constraints

**A stale map is a security bug in both directions** — a task visible to someone who
should not see it, or hidden from someone who should. This is denormalization on the
authorization path, so it needs deliberate machinery, not a trigger bolted on:

- Recompute the affected task's rows **in the same transaction** as any
  `SubTaskImageLink` insert/delete. These go through the task service, so the write
  points are bounded and enumerable.
- **Patient project reassignment invalidates tasks transitively** and does not go
  through the task service at all. This is the case that will bite; handle it
  explicitly rather than discovering it in production.
- A reconciliation job that recomputes from the graph and diffs, plus a test that
  asserts the materialized map equals the walked map on a seeded dataset. That test
  is what makes the denormalization safe to trust.
- Keep `_set_valued_predicate`'s graph walk as the **definition of truth**. The
  materialized map is then an optimization of a specified behaviour, and the
  recompute-and-compare test has something to compare against.

Needs a backfill migration (generated via `revision --autogenerate`, then reviewed —
never hand-written).

## Rejected alternatives, with evidence

Both were measured on 2026-08-07 under the old 128 MB buffer pool, so read the two
absolute figures below as ratios against the 1.6 s baseline of that day, not against
the 0.31 s one above. Neither conclusion depends on the constant.

- **Two covering indexes** `ImageInstance (ImageInstanceID, SeriesID)` and
  `Series (SeriesID, StudyID)`. The mechanism is sound — `ImageInstance` already
  carries `fk_ImageInstance_Series1_idx (SeriesID)`, which InnoDB stores as
  `(SeriesID, ImageInstanceID)`, the same two columns mirrored; scanning all
  1,847,932 entries costs 491 ms versus 555 ms for 85k clustered lookups, so a
  two-int index is ~20× denser than the 528-byte clustered row. But it is a
  constant-factor patch on a linear problem, it adds ~60–80 MB of index and
  permanent write amplification to `ImageInstance` (the importer's hottest table),
  and MySQL may not even choose a PK-prefixed covering index over `PRIMARY` for an
  `eq_ref`. Dropped from Task 12 for those reasons.
- **Rewriting the predicate to walk downward** (`Patient → Study → Series →
  ImageInstance → link`), which would use only existing indexes. Measured: MySQL
  reorders it straight back to the identical plan, **1,753 ms**. Join order in the
  SQL text is not a lever here. The plan's "do not restructure the predicate"
  instruction is correct and now proven.

## Separate, do regardless — DONE

The buffer pool is off MySQL's 128 MB default: `c9fcb56f` (2026-08-18) set
`--innodb-buffer-pool-size=${EYENED_DATABASE_BUFFER_POOL_SIZE:-2G}` in
`database/docker-compose.yaml`, documented in `database/.env.example` and
`database/README.md`. The live server reports 2147483648. It did **not** substitute
for the materialized map — see the growth table.

## Before committing to any of this

Every number here describes an 87,454-link snapshot. Generate a 10× dataset on a
non-shared instance and re-measure before implementing — it is cheap to falsify the
extrapolation, and better done now than after a migration. Add a latency-budget
assertion on the tasks listing either way, so the cliff surfaces as a failing check
rather than as a user report.
