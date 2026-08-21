# `alembic upgrade --sql` writes the confirmation prompt into the generated SQL

**Found:** 2026-08-20, while fixing the `alembic stamp` squash-cutover defect.
**Status:** recorded, not repaired.

`orm/migrations/alembic/env.py`'s confirmation guard writes to stdout (`input(...)`
for the interactive prompt, `print(...)` for the `EYENED_ALEMBIC_ASSUME_YES` notice).
So does `alembic upgrade --sql`, which is meant to emit *only* SQL. The two
interleave: the redirected output starts with the prompt text glued onto the first
line of real SQL, not SQL alone.

Measured: `echo 'y' | alembic upgrade base:orm_baseline --sql > out.sql` from
`orm/migrations` (dummy `EYENED_DATABASE_USER`/`PASSWORD`, no real DB needed --
offline mode never connects) produced this as line 1 of `out.sql`:

```
Target database: probe_user@database:3306/eyened_database. Proceed? [y/N] CREATE TABLE alembic_version (
```

`orm/migrations/generate_latest_migration_sql.sh` hits this on every run --
`echo 'y' | alembic upgrade "$current_rev:$head_rev" --sql > "$tmp_sql"` -- so
`sql/latest_migration.sql` carries the prompt line as a prefix to its first
statement today.

Repair means moving the prompt (and the assume-yes notice) to stderr, or skipping it
in `--sql`/offline mode. Either touches `orm/migrations/alembic/env.py`, which
`orm/eyened_orm/tests/test_alembic_env_read_order.py` pins by AST (read order ahead
of `load_env_file`, the confirmation call's existence, `compare_type`, `render_item`)
-- a fix has to keep those assertions true, and
`test_the_confirmation_prompt_still_exists` would need updating too if the prompt
moves to a different call. Not in scope for the squash-cutover doc/CI fixes;
recorded here instead.
