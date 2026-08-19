# Task→project map: materialize it, or task listings degrade linearly with image links

**Status:** open

## Source

RBAC multi-project enforcement work, branch `feature/rbac-multi-project-tasks`,
during the task that scopes `Task` and `SubTask` reads (the containment rule at
the API). The plan it came from is a working document that is not tracked in
this repository, so it is named here rather than linked.

Measured on the shared dev MySQL 8.0.27 (`eyened-gpu:8983`) on 2026-08-07, with
read-only `EXPLAIN ANALYZE` / `SELECT` only. The plan's Task 12 block originally
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

The map is **43 rows** today. It grows with tasks × projects-per-task, not with
images.

## Why

Once task reads are scoped, the predicate costs **O(total `SubTaskImageLink`
rows) per request** for every non-administrator, independent of how many tasks
the caller can see and of `LIMIT`. (An administrator pays nothing: `apply_scope`
returns the statement untouched. And nothing pays it *today* — no repository
applies this predicate yet, so the figures below were measured by running it by
hand, not by timing a live endpoint.) MySQL decorrelates the `NOT EXISTS`, dropping the `sib.TaskID = t.TaskID`
correlation, so it computes the task→project map for *every* task, materializes it
with deduplication, and then antijoins. The antijoin itself is free
(`Single-row index lookup on <subquery2>`, 0.000 ms/row); the whole cost is the one
materialization. That is why the figure is the same whether the outer table is
`Task` (46 rows) or `SubTask` (19,207), and why `LIMIT 50` does not help.

Measured baseline, three warm runs: **1,640 / 1,672 / 1,653 ms**. Per-hop
increments, all driving the same 85,454 loops:

| hop | table size | increment |
|---|---|---|
| `SubTask` → `SubTaskImageLink` | 4 MB | 72 ms |
| → `ImageInstance` (PK) | 909 MB | **+955 ms** |
| → `Series` (PK) | 123 MB | **+448 ms** |
| → `Study` (PK) | 11 MB | +64 ms |
| → `Patient` (PK) | 7 MB | +71 ms |

Cost tracks **table size, not row count** — `Study` does the same 85,454 clustered
lookups over 210k rows in 64 ms. The variable is whether the table fits in cache;
see the buffer-pool note below.

**The growth argument is the reason this is worth doing.** Constant-factor fixes
(buffer pool, covering indexes) buy roughly 5–8× and 4–5× respectively. The cost is
linear in `SubTaskImageLink`, so one order of magnitude of data growth consumes the
entire budget:

| `SubTaskImageLink` rows | today | with both constant-factor fixes (est.) |
|---|---|---|
| 85k (now) | 1.6 s | ~0.2 s |
| 850k (10×) | ~16 s | ~2 s |
| 8.5M (100×) | ~160 s | ~20 s |

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

## Separate, do regardless

**`innodb_buffer_pool_size` is 128 MB** — MySQL's untouched default — against a
5.3 GB database, a 909 MB `ImageInstance`, and a 62 GB host with 35 GB free. All
8,192 pages allocated, zero free. Nothing in `database/docker-compose.yaml` sets it.

This is misconfiguration rather than a tuning choice, it is free, it needs no code
or migration, and it helps every query in the system — but it belongs to the
deployment work, not to this item, and it does **not** substitute for the
materialized map (see the growth table).

⚠️ Changing it restarts a container shared with other users' workloads on this host;
coordinate before doing it.

## Before committing to any of this

Every number here describes an 85,454-link snapshot. Generate a 10× dataset on a
non-shared instance and re-measure before implementing — it is cheap to falsify the
extrapolation, and better done now than after a migration. Add a latency-budget
assertion on the tasks listing either way, so the cliff surfaces as a failing check
rather than as a user report.
