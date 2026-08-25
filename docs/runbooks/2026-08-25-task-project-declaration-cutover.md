# Task project declaration cutover — deploying `2db0e63195db`

> Preparer: replace `<contact>` below with a real name and channel before sending this to a site, then delete this line.

**Contact:** `<contact>`

Five migrations, `d3ce100ab2b6` through `2db0e63195db`, denormalize `ProjectID` down the patient chain and add the `TaskProject` declaration the read path switches to.

The chain and the release are not independent. The chain adds `NOT NULL` columns with no default, so the **previous** release cannot INSERT once it is applied — the importer included — and the new release cannot SELECT before it. Apply the chain and deploy in one window, chain first. Run once per site.

## Rules

- Run every Alembic command from `orm/migrations`, with `-x env_file=` **before** the subcommand: `alembic -x env_file=<ddl.env> upgrade head`.
- Alembic needs the `eyened_ddl` credentials. The server container runs as `eyened_wr`, which holds no DDL rights.
- Take a full backup immediately before step 2.
- **Stop every writer for the whole of step 2** — API and importer. A write taken between `99724789b34d` and `2db0e63195db` can abort the chain; see Recovery.
- `upgrade` prompts `Target database: ... Proceed? [y/N]`. Without a TTY it raises an uncaught `EOFError`; `EYENED_ALEMBIC_ASSUME_YES=1` skips the prompt for one command. `current`, `heads` and `check` never prompt.
- Do not run any of this with `foreign_key_checks` off. The migrations refuse; off, `ADD FOREIGN KEY` creates a key that has never looked at a row.
- Do not re-run a failed migration over its result without reading Recovery first. MySQL commits DDL implicitly.
- Take the head from `alembic heads` on the release checkout, not from this document. If other migrations land after this one, the chain is rebased and the id below is no longer the target.
- Anything that does not match this document: stop before the next command and contact `<contact>`.

## Timing

Measured on a copy of the dev database — 1,852,297 images, 1,196,373 series, 212,095 studies, 87,454 subtask→image links — on MySQL 8.0.27 with a 2 GB buffer pool.

| Revision | Does | Measured | Writes |
|---|---|---:|---|
| `d3ce100ab2b6` | `ImageInstance.ProjectID` + chunked backfill | 14 min 59 s | served |
| `4eae42457fa2` | `Study.ProjectID`, `Series.ProjectID` + backfills | 3 min 43 s | served |
| `99724789b34d` | `TaskProject` + backfill from the image links | 4.8 s | served |
| `b45090e1544e` | composite foreign keys | 9 min 16 s | **blocked 9 min 7 s** |
| `2db0e63195db` | `SubTaskImageLink` containment | 43.8 s | brief |
| **total** | | **28 min 47 s** | |

`b45090e1544e` is the window to plan around. Its three `ADD CONSTRAINT ... ALGORITHM=COPY, LOCK=SHARED` statements rebuild the table, so they **cost by the table's size on disk, not its row count**: 8.5 s for `Study` (47 MB), 148 s for `Series` (532 MB), 390 s for `ImageInstance` (1.76 GB) — around 0.2 s per MB. Reads are served throughout.

Take the three table sizes from production's own `information_schema.TABLES` (`DATA_LENGTH + INDEX_LENGTH`) and scale from them. Do not scale from the row counts above.

The migrated schema costs **+17%** over the same rows.

## Steps

**0. Preconditions.** All on the target database, before anything else.

| Check | Expect |
|---|---|
| `alembic -x env_file=<ddl.env> current` | `orm_baseline`. A later id means the chain was rebased — stop and contact `<contact>` |
| `SELECT @@SESSION.sql_mode` | contains `STRICT_TRANS_TABLES` or `STRICT_ALL_TABLES` |
| `SELECT @@GLOBAL.binlog_format` | `ROW` — the backfills fail with ERROR 1665 under `STATEMENT` |
| `SELECT @@SESSION.foreign_key_checks` | `1` |
| free disk | at least the size of `ImageInstance`, plus 17% of the schema |

No part of this repository sets `sql_mode` or `binlog_format`; they are the server's. Anything else here: stop and contact `<contact>`.

**1. Stop the writers.** API and importer both. Reads may continue.

**2. `alembic -x env_file=<ddl.env> upgrade head`** — real DDL, roughly 30 minutes at dev scale plus whatever step 0's sizes imply. Back up first.

- Expect: five revisions apply, the last being `2db0e63195db`.
- On any failure: Recovery, below. Do not re-run blind.

**3. `alembic current`, then `alembic check`** — the gate. Do not deploy until it passes.

- Expect: `2db0e63195db (head)` and a clean check.
- Otherwise: stop before step 4 and contact `<contact>`.

**4. Deploy the release.**

**5. Restart the writers, then verify.**

- `eorm check-declarations` — reports declarations no image link uses. Rows here are legal and fail-safe; record them, do not act.
- Open the tasks page as a non-admin member and confirm the tasks they expect are listed.

## Recovery and rollback

| Situation | Action |
|---|---|
| `2db0e63195db` aborts: `N (task, project) pairs are reachable through the image links but not declared in TaskProject ... Reconcile first` | A writer was live during step 2. The gate runs before any DDL, so nothing is half-applied and the database sits at `b45090e1544e`. Stop the writer, insert the missing pairs into `TaskProject`, re-run `upgrade head`. Contact `<contact>` for the reconciling statement — declaration management does not ship in this release. |
| `2db0e63195db` prints `NOTE: N declared (task, project) pairs no link uses` | Not an error, the migration continues. Those tasks become harder to see once the read path switches. Record and continue. |
| A migration fails part-way, or the run is interrupted | Every migration in the chain is re-runnable — each step is guarded by the state it would produce. Run `alembic current`, then `alembic upgrade head` again. If `current` names a revision you do not expect, stop and contact `<contact>`. |
| Roll back before step 4 | `alembic downgrade orm_baseline`. **16 min 14 s** at dev scale, of which `b45090e1544e` blocks writes for a further **8 min 19 s** re-copying the same three tables. Restoring the backup is faster if the window is still open. |
| Roll back after step 4 | The previous release cannot write to the migrated schema, so code alone is not enough: redeploy the previous release **and** downgrade, in that order, at the cost above. |
| Downgrade past `99724789b34d` | Drops `TaskProject`. Declarations broader than a task's images are derived from nothing and do not come back — re-applying the chain re-derives only what the links imply. Note any task created after step 4 before downgrading. |
| Step 2's DDL must be undone entirely | Redeploy the previous release **first**, then restore the pre-step-2 backup — only while the window is still open. Once the new release has taken writes, restoring loses them: contact `<contact>` instead. |
