# `alembic upgrade --sql` writes the confirmation prompt into the generated SQL

**Found:** 2026-08-20, while fixing the `alembic stamp` squash-cutover defect.
**Status:** done — repaired in PR #222.

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

## Repair

The guard now writes to stderr throughout. The assume-yes notice and the abort
message take `file=sys.stderr`; the interactive prompt is printed to stderr and
`input()` is called with no argument, since `input`'s own prompt goes to stdout.

`test_the_confirmation_prompt_still_exists` needed no change -- `input()` is still
called at module level, only without its prompt argument. A new sibling,
`test_the_confirmation_guard_writes_only_to_stderr`, pins the fix: every
module-level `print(...)` must pass `file=sys.stderr`, and no module-level
`input(...)` may take a prompt argument. Against the unfixed `env.py` it fails and
the other four assertions still pass.
