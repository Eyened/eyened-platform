# A large `IN` list makes MySQL abandon the range optimizer and full-scan `ImageInstance`

**Status:** open

## Source

Found in flight while measuring something else: a performance gate on branch
`feature/tasks-page-performance` comparing composite-foreign-key read cost against a
single-column control (2026-08-20). The hazard showed up in **both** shapes, so it is
unrelated to that change and outlives it.

## What

`SELECT ... FROM ImageInstance WHERE ImageInstanceID IN (...)` with a **14,014-element**
list makes MySQL 8.0.27 give up on the range optimizer and full-scan `ImageInstance`
(1.86 M rows, **~2.3 s**). The same query with a **2,000-element** list still uses a
range scan and is fast.

Measured on a throwaway `mysql:8.0.27` with `--innodb-buffer-pool-size=2G`, against a
fixture whose row counts and fan-out ratios match production aggregates.

The 14,014 figure is not hypothetical: it is the link count of task 70, the largest task
in the live database. What was measured was a synthetic query, not a request — the open
question is whether any production path actually builds an `IN` list of that size. The
shapes to check are the ones that collect ids and then load them in one go: `selectin`
eager loads over a large collection, and any repository method that takes a list of ids
straight from a caller.

**Cause not established.** The measurement recorded the plan change, not the reason for
it. The documented mechanism that fits is `range_optimizer_max_mem_size` (default 8 MB),
which bounds the memory the range optimizer may use and makes MySQL fall back to a scan
rather than error when exceeded — it emits warning 3170 when it does, so whoever picks
this up can confirm or rule it out in one query. If that is the cause, raising the
variable is one option, but chunking the `IN` list is the fix that does not depend on a
server setting.

## Why

~2.3 s on one statement is roughly **10×** the entire cost of the composite-key change
the gate was convened to judge, and about the size of the regression the tasks-page work
existed to remove in the first place. It also fails quietly — the query returns correct
rows, so nothing surfaces except latency, and it degrades with data growth rather than
appearing at a threshold anyone would notice in review.

If no production path builds a list that large today, this is cheap to close: confirm it,
write down where the ceiling is, and move on. That confirmation is the work.
