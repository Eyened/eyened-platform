# Migration drift has no CI gate — and cannot have one until a baseline exists

**Status:** open

## Source

Found while investigating why the `dev-kaustav` database was a revision behind
(`624c5700c50f` vs head `a1d1700000a1`, the `AuditLog` table missing). Applying
that migration was the immediate fix; this entry is the systemic gap behind it.
All findings below were verified empirically on 2026-07-30, not inferred.

## What

Three separate pieces, in dependency order. The first blocks the other two.

### 1. The migration chain cannot build a database from scratch

`alembic upgrade head` against an empty MySQL 8.0.27 dies on the second revision:

```
Running upgrade  -> 832ed384515f, new image hash and study round columns
Running upgrade 832ed384515f -> e69c5e4002ed, segmentation_update
pymysql.err.ProgrammingError: (1146, "Table 'eyened_database.Contact' doesn't exist")
```

The root revision is a stub, not a baseline
(`orm/migrations/alembic/versions/2025_04_03-new_image_hash_and_study_round_columns.py:14`):

```python
"""Revision ID: 832ed384515f
Revises: e2fb79ea7982      # parent named in the docstring...
"""
down_revision = None       # ...but severed here
def upgrade() -> None:
    pass                   # and it does nothing
```

History was truncated and `down_revision` set to `None` without writing a baseline
to replace what was cut. `e2fb79ea7982` is not in the repo. `Base.metadata` declares
**43 tables**; `create_table` appears for only 19 names, two of which (`Attributes`,
`ImageAttributes`) are no longer in the model — so **~26 of the 43 live tables are
created by no migration at all**. They exist only because every real database is a
physical descendant of the original production one, which is why `database/load_dump.sh`
restores via `xtrabackup --copy-back` rather than migrating.

**Fix:** cut a baseline revision from current `Base.metadata`, make it the new root,
archive the 23 existing files, and `alembic stamp <baseline>` every environment.
The alternative — reconstructing the pre-`832ed384515f` schema to preserve the
23-step history — buys nothing: the history is already severed and no environment
needs to replay it, since all are at or near head.

Two sequencing constraints:

- `alembic check` is currently **red** on a pre-existing drift (missing index
  `StorageBackendID_ObjectKey` on `ImageStorage`, from `origin/importer-update`).
  Write that migration and get `check` clean *before* cutting the baseline, or the
  drift is baked in permanently.
- Charset. `AuditLog` was created `DEFAULT CHARSET=utf8mb3`, inherited from the
  database default. A baseline applied to a fresh MySQL 8 yields `utf8mb4` and
  `alembic check` will then flag every table forever. Pin the charset explicitly
  in the baseline and in any CI service container.

### 2. `env.py` is not CI-safe

`orm/migrations/alembic/env.py:60` prompts via `input()` for any command that
alters the database. With no TTY this raises `EOFError` and `alembic upgrade`
cannot run at all — verified.

**Fix:** an explicit `ALEMBIC_ASSUME_YES` env-var escape hatch. Do *not* make it
auto-detect a non-TTY: that would silently auto-approve any script or cron job
pointed at production, which is exactly what the prompt exists to prevent.

### 3. The gate itself

Once (1) and (2) land — a `migrations-ci.yml` on `orm/**` paths with a
`mysql:8.0.27` service container:

```
alembic upgrade head          # chain executes on real MySQL from scratch
alembic check                 # resulting schema == Base.metadata
[ $(alembic heads | grep -c '(head)') -eq 1 ]
```

Leave `alembic downgrade base` out initially — downgrades are typically rotten in
a forward-only shop and would produce a lot of red for little value.

**Available today, with no prerequisites:** the head-count check needs no database.
Verified running with deliberately bogus credentials — exit 0, one head. It is a
sub-second step that could go into `server-ci.yml` now, and it catches two people
branching off the same parent and each adding a migration.

## Why

The test suite is structurally blind to migration drift.
`orm/eyened_orm/utils/sqlite_testdb.py:69` builds every test schema with
`Base.metadata.create_all(engine)` — generated **from the models**. Not one
migration is executed by any of the 276 tests. The suite proves the models are
self-consistent and says nothing about whether the migrations reproduce them.

**Risk if left undone:** a PR can change a model, ship no migration, and stay green
forever. The gap only surfaces at deploy time against a real database, as a 500 on
a missing column or table. The `StorageBackendID_ObjectKey` index is a live example
already sitting in the tree.

## Related — environment drift is a different problem

A *specific database* being behind the chain is not CI-gateable; it is a property of
a running environment, not of the code. Two separate mitigations:

- A startup check comparing `MigrationContext.get_current_revision()` against
  `ScriptDirectory.get_current_head()`, refusing to boot (or logging loudly) on
  mismatch.
- `database/load_dump.sh` does `rm -rf /var/lib/mysql/*` then `xtrabackup --copy-back`
  — a physical restore that replaces the `mysql` system schema along with the data.
  Every dump reload therefore rewinds `alembic_version` to production's revision
  *and* destroys any locally minted DDL account. Folding `alembic upgrade head` into
  the tail of that script removes the recurrence.
