# Schema-sync CI baseline

`baseline.sql` in this directory is a frozen snapshot of Erasmus production's schema
plus its single `alembic_version` row. It is CI input only.

**DO NOT LOAD THIS INTO A LIVE DATABASE.** The schema-sync CI job loads it into a
throwaway MySQL container, runs `alembic upgrade head` to replay the revisions added
since it was frozen, and asserts that `alembic check` reports no operations. There is
no `alembic stamp` step anywhere in the workflow — the file already carries the
`alembic_version` row that makes Alembic know where it stands.

This is a **frozen artifact**. New Alembic revisions replay on top of it; it is not
refreshed as part of normal development. It is not scripted into the repo because a
committed generator for a once-only snapshot would be dead code the day it lands.
This README is the regeneration procedure, to be followed by hand if the baseline
ever needs to move forward (e.g. a future re-baseline, or if the whole
`orm/migrations/baseline/` directory is retired — see "Retirement" below).

## Provenance

- Source: XtraBackup of Erasmus production, taken 2026-07-28
  (`backup_type=full-prepared`, `server_version=8.0.27`, `partial=N`, `encrypted=N`),
  stored at `database/tmp/eyened_dump` in the main checkout (8.8 GB, root-owned,
  outside git).
- Restored into a throwaway MySQL 8.0.27 container on 2026-08-17.
- Restored database: `eyened_database`.
- Revision, read by `SELECT version_num FROM alembic_version` (the only authority —
  not inferred, not guessed): **`a1d1700000a1`** (`2026_07_24-add_audit_log.py`).
  This leaves two revisions to replay in CI: `c3f5a2b81d94`
  (`restrict_tag_deletes`) and `b2e2800000b2` (`rbac_project_member`).
- Table inventory at that revision: `BASE TABLE` = 44 (43 ORM-modelled tables +
  `alembic_version`), `VIEW` = 6.

## Excluded on purpose: the six views

Erasmus production carries six views, all `DEFINER=root@%`, made by hand on the
production box:

- `ProjectToFeature`
- `ProjectToImageInstance`
- `ProjectToImageStorage`
- `ProjectToSubtask`
- `ProjectToTag`
- `Statistics`

No Alembic migration creates them, the SQLAlchemy ORM does not model them, and
nothing else in this repo references them by name. They are excluded from the
baseline by construction: the dump in Step 4 below names an explicit list of base
tables rather than dumping the whole database, so the views (and the stored routine
`BenchmarkQuery`, and all triggers) never appear in `baseline.sql`. This is also the
only reliable way to exclude them — `mysqldump` has no `--no-views` flag.

They cannot affect the CI gate either way: SQLAlchemy's MySQL dialect reflects base
tables only (`dialects/mysql/base.py:3290`), so Alembic never sees a view regardless
of whether it's present in the loaded database.

**If regenerating:** always derive the table list from a live query
(`information_schema.tables` filtered to `table_type='BASE TABLE'`) rather than
hardcoding six `--ignore-table` flags — that keeps the exclusion correct if
production gains another view later. If a regeneration finds a different number or
set of views than the six above, that is worth recording as a finding, but the
exclusion logic (by table type, not by name) still holds.

## STOP conditions (from the original freeze, and for any regeneration)

Do not produce a baseline past any of these:

- `alembic_version` returns more than one row, or zero rows.
- The revision is not one of the ids present in `orm/migrations/alembic/versions/`.
  Verify with `command grep -rl "<revision>" orm/migrations/alembic/versions/*.py`.
  A baseline whose revision Alembic cannot locate makes `upgrade head` fail with
  "Can't locate revision identified by …".
- The revision is one nobody recognises as an Erasmus production revision. A
  baseline from an unidentified database is worse than no baseline.
- The table-list diff (Step 3 below) between production's base tables and
  `Base.metadata` shows anything beyond the tables that later migrations are known
  to create. A `<` line (a production table the ORM does not model) makes
  `alembic check` propose dropping it; an unexpected `>` line (an ORM table
  production lacks, beyond what's expected) makes `check` propose creating it.
  Either means the design needs an `include_object` filter before it can ship — a
  decision, not a fix to improvise mid-procedure.
- `BASE TABLE` count, or the count of names in the table list actually dumped, is
  not exactly what the derivation predicts (at the 2026-08-17 freeze: 44 — 43 ORM
  tables plus `alembic_version`). A wrong count there is a wrong baseline.

If a regeneration hits any of these, stop, tear down the container and working
copy, and report — do not adjust the expectation to match what was found.

## Regeneration procedure

This is a manual, once-only-per-freeze procedure. It runs against a **copy** of the
production backup in a **throwaway** container; it never touches the original
backup, which must stay mounted `:ro` throughout.

Environment:

```bash
WT=<path to a worktree of this repo>
MAIN=<path to the main checkout, containing database/tmp/eyened_dump>
PY="$MAIN/dev/.venv/bin/python"
export PYTHONPATH="$WT/orm"
```

Verify `PYTHONPATH` actually points at the checkout you're working from — the
venv's `eyened_orm` is an editable install that otherwise resolves against
`$MAIN`, silently comparing against the wrong ORM model set:

```bash
PYTHONPATH="$WT/orm" "$PY" -c "import eyened_orm; print(eyened_orm.__file__)"
```

### Step 1: Confirm disk headroom and make the working copy

The backup is ~8.8 GB and root-owned. Copy it through a container so no host
`sudo` is needed, chowning to MySQL's uid (999) in the same pass.

```bash
df -h /var/tmp | tail -1          # need >= 10G available
BASE=/var/tmp/eyened-baseline-datadir
mkdir -p "$BASE"
docker run --rm \
  -v "$MAIN/database/tmp/eyened_dump":/src:ro \
  -v "$BASE":/dst \
  alpine:latest sh -c 'cp -a /src/. /dst/ && chown -R 999:999 /dst'
```

Verify the copy's size with a container (the host user loses read access to the
chowned tree):

```bash
docker run --rm -v "$BASE":/dst:ro alpine:latest du -sh /dst
```

Expected: ~8.8G. The `:ro` mount on `/src` is what keeps the only copy of the
backup safe.

### Step 2: Boot a throwaway MySQL on the copy

The restored datadir carries production's `mysql.user` table, so
`MYSQL_ROOT_PASSWORD` does not apply and production's root password is unknown.
`--skip-grant-tables` gives passwordless local access and disables networking,
which is fine — every command goes through `docker exec` over the unix socket. No
host port is published.

```bash
docker run -d --name eyened-baseline-tmp \
  -v /var/tmp/eyened-baseline-datadir:/var/lib/mysql \
  mysql:8.0.27 --skip-grant-tables
timeout 180 bash -c 'until docker exec eyened-baseline-tmp mysqladmin ping --silent 2>/dev/null; do sleep 3; done'
```

**If the container exits instead**, check `docker logs eyened-baseline-tmp` for a
redo-log format complaint. The backup as of the 2026-08-17 freeze was prepared by
XtraBackup 8.0.35, which writes an (empty) `#innodb_redo/` directory belonging to
the 8.0.30+ layout even though `server_version` reports 8.0.27. If 8.0.27 refuses
it, retry with `mysql:8.0.35`, then `mysql:8.0.46`. **This does not change the CI
pin.** CI loads a SQL text dump into a freshly initialised datadir, so the server
version that reads this backup and the server version CI runs are independent; CI
stays on 8.0.27 because that is production's version.

### Step 3: Establish provenance — the `SELECT` is the authority

```bash
docker exec eyened-baseline-tmp mysql -uroot -N -B -e "SHOW DATABASES"
docker exec eyened-baseline-tmp mysql -uroot -N -B -e \
  "SELECT version_num FROM eyened_database.alembic_version"
docker exec eyened-baseline-tmp mysql -uroot -N -B -e \
  "SELECT table_type, COUNT(*) FROM information_schema.tables
   WHERE table_schema='eyened_database' GROUP BY table_type"
docker exec eyened-baseline-tmp mysql -uroot -N -B -e \
  "SELECT table_name FROM information_schema.tables
   WHERE table_schema='eyened_database' AND table_type='VIEW' ORDER BY table_name"
```

Then run the table-list diff — the check that decides whether the gate can ever be
green:

```bash
docker exec eyened-baseline-tmp mysql -uroot -N -B -e \
  "SELECT table_name FROM information_schema.tables
   WHERE table_schema='eyened_database' AND table_type='BASE TABLE' ORDER BY table_name" \
  > /var/tmp/baseline-tables.txt
PYTHONPATH="$WT/orm" "$PY" -c \
  "from eyened_orm.base import Base; import eyened_orm; print('\n'.join(sorted(Base.metadata.tables)))" \
  > /var/tmp/metadata-tables.txt
command grep -v '^alembic_version$' /var/tmp/baseline-tables.txt > /var/tmp/baseline-tables-notver.txt
diff /var/tmp/baseline-tables-notver.txt /var/tmp/metadata-tables.txt
```

At the 2026-08-17 freeze the only difference was `> ProjectMember`, the table that
`b2e2800000b2` creates during replay — expected, since that revision had not yet
been applied to the restored database. See STOP conditions above for what any other
diff output means.

### Step 4: Dump schema and version row

```bash
set -euo pipefail
mkdir -p orm/migrations/baseline

docker exec eyened-baseline-tmp mysql -uroot -N -B -e \
  "SELECT table_name FROM information_schema.tables
   WHERE table_schema='eyened_database' AND table_type='BASE TABLE' ORDER BY table_name" \
  > /var/tmp/basetable-names.txt
wc -l /var/tmp/basetable-names.txt    # expect 44 — stop if it is not
tr '\n' ' ' < /var/tmp/basetable-names.txt > /var/tmp/tables-oneline.txt

TABLES=$(cat /var/tmp/tables-oneline.txt)
docker exec eyened-baseline-tmp mysqldump -uroot \
  --no-data --skip-comments --skip-routines --skip-triggers \
  --no-tablespaces --set-gtid-purged=OFF \
  eyened_database $TABLES > /var/tmp/baseline-schema.sql

docker exec eyened-baseline-tmp mysqldump -uroot \
  --no-create-info --skip-comments --skip-triggers \
  --no-tablespaces --set-gtid-purged=OFF \
  eyened_database alembic_version > /var/tmp/baseline-version.sql
```

Flag notes — do not drop or "simplify" any of these:

- Naming the tables explicitly (rather than dumping the whole database) is what
  excludes the six views: `mysqldump` has no `--no-views` flag, and an explicit
  table list is the supported way to exclude them.
- `--skip-routines` keeps out stored procedures (`BenchmarkQuery`) that neither
  the ORM nor Alembic manages.
- `--skip-triggers` does the same for triggers — which `mysqldump` emits **by
  default** and which `--skip-routines` does not cover. Both routines and triggers
  would otherwise carry a production `DEFINER` clause for a user that does not
  exist in CI.
- `--no-create-info` on the *second* dump (the `alembic_version` data dump) is
  what keeps `alembic_version` from being created twice. The schema dump already
  defines the table; without this flag the assembled file carries a redundant
  `DROP TABLE` + `CREATE TABLE` pair, and the `CREATE TABLE` count in Step 5/6
  comes out one higher than expected (45, not 44) — and the file drops the row
  the schema dump created moments earlier before re-adding it.
- `--no-tablespaces` avoids a `PROCESS`-privilege failure mode if this is ever
  re-run as a non-root user.
- `--set-gtid-purged=OFF` keeps a `SET @@GLOBAL.GTID_PURGED` statement out of a
  file that gets loaded into a fresh CI server. Both of these are no-ops in the
  happy path but are cheap insurance.

### Step 5: Verify the dumps are complete before assembling

```bash
command grep -c "^CREATE TABLE" /var/tmp/baseline-schema.sql || true          # expect 44
command grep -c "^INSERT INTO \`alembic_version\`" /var/tmp/baseline-version.sql || true   # expect 1
command grep -c "^CREATE TABLE" /var/tmp/baseline-version.sql || true         # expect 0 — --no-create-info
tail -c 300 /var/tmp/baseline-schema.sql                       # expect the /*!40xxx SET ... */ restore block
command grep -c "StorageBackendID_ObjectKey" /var/tmp/baseline-schema.sql || true  # expect 0
command grep -cE "^(CREATE|/\*!50001 CREATE).*(VIEW|TRIGGER)" /var/tmp/baseline-schema.sql || true  # expect 0
command grep -c "DEFINER" /var/tmp/baseline-schema.sql || true                # expect 0
```

Notes:

- `grep -c` exits 1 when the count is zero, which would kill the shell under
  `set -euo pipefail` precisely when a check passes — `|| true` keeps the count
  printing and the shell alive.
- `grep` in this environment may be a `ugrep --ignore-files` wrapper in some
  shells; a count of zero from it is not reliable evidence on its own, so every
  check whose *absence* is the finding should use `command grep`.
- The last two checks (`VIEW`/`TRIGGER` and `DEFINER`) are what prove the
  base-table list in Step 4 actually excluded the six views. A non-zero count on
  either means the whole database got dumped after all.
- The `StorageBackendID_ObjectKey` check matters for a later CI-gate task:
  Erasmus production has never had that composite index, so the baseline must
  not contain it either.
- 44 `CREATE TABLE` statements is the derived figure (43 ORM tables at the frozen
  revision, plus `alembic_version`), not an approximation. A different number
  means the diff in Step 3 was misread — go back rather than adjusting the
  expectation.

### Step 6: Assemble `baseline.sql` with its header

Concatenate a header (recording the real provenance values from Step 3 — database
name, revision, table counts, view list, backup metadata) with the schema dump and
the version dump, in that order, into `orm/migrations/baseline/baseline.sql`. See
the top of `baseline.sql` for the exact header format used at the 2026-08-17
freeze.

```bash
command grep -c "^CREATE TABLE" orm/migrations/baseline/baseline.sql || true         # expect 44
command grep -c "^INSERT INTO \`alembic_version\`" orm/migrations/baseline/baseline.sql || true  # expect 1
wc -c orm/migrations/baseline/baseline.sql
```

Expected size: on the order of tens to a few hundred KB — this schema has no row
data. Megabytes would mean row data leaked in; stop and re-dump.

### Step 7: Tear the container and the copy down

Always do this, including on abort:

```bash
docker rm -f eyened-baseline-tmp
docker run --rm -v /var/tmp/eyened-baseline-datadir:/dst alpine:latest sh -c 'rm -rf /dst/* /dst/.[!.]*'
rmdir /var/tmp/eyened-baseline-datadir
ls -la "$MAIN/database/tmp/eyened_dump" | head -3   # confirm the backup itself is untouched
```

`rmdir` fails with `Operation not permitted` here, because Step 1's
`chown -R 999:999 /dst` re-owned the mount point itself and your user no longer
owns it. Remove it through a container instead:

```bash
docker run --rm -v /var/tmp:/varTmp alpine:latest rm -rf /varTmp/eyened-baseline-datadir
```

### Step 8: Commit

```bash
git add orm/migrations/baseline/baseline.sql orm/migrations/baseline/README.md
git commit -m "ci(orm): freeze Erasmus schema baseline for the schema-sync gate"
```

## Retirement

This directory is deleted when the #186 baseline squash lands (spec §8). At that
point Alembic's own migration history becomes the baseline and this frozen SQL
snapshot, and the CI gate that loads it, are no longer needed.
