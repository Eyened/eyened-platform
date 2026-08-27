# Task project declaration cutover — deploying `2db0e63195db`

Five migrations, `d3ce100ab2b6` through `2db0e63195db`, denormalize `ProjectID` down the patient chain and add the `TaskProject` declaration the read path switches to.

**The service is down for all of it.** The chain adds `NOT NULL` columns with no default, so the previous release cannot INSERT once it is applied — the importer included — and the new release cannot SELECT before it. There is no ordering that keeps the site up, and nothing here tries to.

Budget **~30 minutes of downtime at dev scale**, plus the restore time of your backup. Run once per site.

## Before you start

Check on the target database:

| Check | Expect |
|---|---|
| `alembic -x env_file=<ddl.env> current` | `orm_baseline`. A later id means the chain was rebased — stop and escalate |
| `SELECT @@SESSION.sql_mode` | contains `STRICT_TRANS_TABLES` or `STRICT_ALL_TABLES` |
| `SELECT @@GLOBAL.binlog_format` | `ROW`, unless you disable the binary log in step 3 — the backfills fail with ERROR 1665 under `STATEMENT` |
| `SELECT @@SESSION.foreign_key_checks` | `1`. Never turn this off to go faster: the foreign keys are the point of the release, and added with checks off they are never validated against the rows already in the table |
| free disk | at least the size of `ImageInstance`, plus 17% of the schema |
| `eorm check-dangling-references` | `No dangling references (5 hops checked).` |

**If the dangling-reference check is not clean.** Each line names a child table whose parent row is gone, and the `NOT NULL` column whose backfill would resolve to NULL because of it. Left alone, that row stops the chain at `MODIFY ... NOT NULL` with `ERROR 1138 Invalid use of NULL value` — which names no table, no column and no row — part-way into the window, with the schema half changed. Reconcile before step 1: delete the orphaned rows, or restore the parents they point at. The check is read-only, needs only `SELECT`, runs with the application up, and always exits 0 — read its output rather than branching on its status. It takes its connection from `eorm -e <env>`, on the application's own credentials: the DDL account below is not needed, and neither is the window.

Expect it to be clean. Every hop it walks already carries an enforced foreign key with `ON DELETE CASCADE`, so ordinary writes cannot produce one of these rows. The route that stays open is a load with checks off: `mysqldump` output sets `FOREIGN_KEY_CHECKS=0`, so a violating row loads silently and stays. Run it against the restored copy you rehearse on as well as against the target.

Alembic needs the `eyened_ddl` credentials; the server's `eyened_wr` holds no DDL rights. Run every Alembic command from `orm/migrations`, with `-x env_file=` before the subcommand. `upgrade` prompts for confirmation and raises `EOFError` without a TTY — run it interactively or set `EYENED_ALEMBIC_ASSUME_YES=1`.

**Estimating the window.** Almost all of it is InnoDB rewriting two tables. Take `DATA_LENGTH + INDEX_LENGTH` for `ImageInstance` and `Series` from `information_schema.TABLES` and scale from the dev-scale figures below; row counts will mislead, because `ImageInstance` carries 1.5x the rows of `Series` and 2.6x the time.

| Revision | Dev-scale | Dominated by |
|---|---:|---|
| `d3ce100ab2b6` | 14 min 59 s | two rebuilds of `ImageInstance` (1.76 GB), plus a 166 s backfill |
| `4eae42457fa2` | 3 min 43 s | two rebuilds of `Series` (532 MB) |
| `99724789b34d` | 4.8 s | `TaskProject` and its backfill |
| `b45090e1544e` | 9 min 16 s | the composite foreign keys: 8.5 s `Study`, 148 s `Series`, 390 s `ImageInstance` |
| `2db0e63195db` | 43.8 s | `SubTaskImageLink` (87k rows) |
| **total** | **28 min 47 s** | measured twice, within 6% |

## Steps

**1. Stop the application and the importer.** Nothing may write for the rest of this procedure.

**2. Stop the database, then copy its data directory.** This is the backup and the only rollback path. With the server stopped the copy is consistent by construction — no dump, no `--single-transaction`, no prepare step.

```bash
docker compose stop database
docker run --rm -v <db_volume>:/from -v <backup_dir>:/to alpine \
  tar czf /to/pre-cutover.tar.gz -C /from .
```

**3. Start the database.** Plain restart is fine, and the chain will take about as long as the table above says.

*Optional, and untimed:* the compose file passes MySQL one flag, `--innodb-buffer-pool-size`; everything else is 8.0.27 default, including a 48 MB redo log that these rebuilds overrun continuously. For this window only, and only because step 2's copy exists and no user is connected:

```
--innodb-log-file-size=2G
--innodb-buffer-pool-size=<as much as the host will give>
--innodb-flush-log-at-trx-commit=2
--sync-binlog=0
--skip-log-bin          # only with no replica; also drops the binlog_format check
```

Put the normal settings back in step 6. Time a rehearsal both ways before relying on this — the numbers above were measured on the defaults.

**4. `alembic -x env_file=<ddl.env> upgrade head`.**

Expect five revisions to apply, ending at `2db0e63195db`. On failure, see below.

**5. `alembic current`, then `alembic check`.** Do not deploy until this passes.

Expect `2db0e63195db (head)` and a clean check.

**6. Deploy the release.** Restart the database on its normal settings if you changed them in step 3.

**7. Start the application and the importer, then verify.**

- `eorm check-declarations` — reports declarations no image link uses. Legal and fail-safe; record them, do not act.
- Open the tasks page as a non-admin member and confirm the tasks they expect are listed.

## If something goes wrong

**Restore step 2's copy.** That is the rollback, at every point in this procedure. Do not use `alembic downgrade` — it re-copies the same two large tables to undo work you are about to redo, and downgrading past `99724789b34d` drops `TaskProject`, which does not come back for any declaration broader than a task's images.

| Situation | Action |
|---|---|
| A migration fails part-way, or the run is interrupted | Every migration in the chain is re-runnable — each step is guarded by the state it would produce. Run `alembic current`, then `alembic upgrade head` again. If `current` names a revision you do not expect, restore and escalate. |
| A migration aborts: `ERROR 1138 Invalid use of NULL value` | A row's parent is missing, so its backfill resolved to NULL and the `MODIFY ... NOT NULL` refused it. The error names no table, no column and no row: run `eorm check-dangling-references` for all three. It reads only columns that exist on both sides of the chain, so it works on the half-migrated schema you are now looking at. Reaching this means the check in *Before you start* was skipped, or the data changed after it. The column is added and backfilled but still nullable and the revision is not stamped, so the step is re-runnable: reconcile the rows, then `alembic upgrade head`. `2db0e63195db`'s gate does not cover this — it inner-joins `ImageInstance`, so an orphaned link is invisible to it and a clean gate is not evidence. |
| `2db0e63195db` aborts: `N (task, project) pairs are reachable through the image links but not declared in TaskProject ... Reconcile first` | A writer was live during the chain, so step 1 did not hold. The gate runs before any DDL, so nothing is half-applied. Stop the writer and re-run `upgrade head`. |
| `2db0e63195db` prints `NOTE: N declared (task, project) pairs no link uses` | Not an error, the migration continues. Those tasks become harder to see once the read path switches. Record and continue. |
| A problem is found after step 7, with users back on | Restoring loses their writes. Weigh that against the defect and escalate — do not restore reflexively. |
