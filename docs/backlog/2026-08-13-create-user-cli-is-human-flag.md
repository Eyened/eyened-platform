# `eorm create-user --is-human` can never be false

**Status:** open

## Source

RBAC Phase H brainstorming (developer-testability of the admin CLI), branch
`feature/rbac-multi-project-tasks`, 2026-08-13. Deliberately left out of Phase H,
whose scope is the `test_user` UI-testing loop; this flag does not affect it.

## What

`orm/eyened_orm/cli.py` declares the option as:

```python
@click.option("--is-human", is_flag=True, default=True)
```

A Click flag with `default=True` and no off-switch is always true: passing
`--is-human` sets it true, omitting it falls back to true, and there is no
`--no-is-human` to set it false. So `create_user(..., is_human=...)` is called
with `True` on every invocation and the parameter is dead.

Fix is one line — `"--is-human/--not-human", default=True` — plus a test that
the false path reaches the `Creator` row.

While in there: `create_user` in `orm/eyened_orm/utils/db_users.py` also accepts
`employee_identifier`, which the CLI does not expose.

## Why

No non-human `Creator` (AI model, attribution-only account) can be minted from
the CLI. That matters for `grant_all`, which selects on
`Creator.IsHuman.is_(True)` (`orm/eyened_orm/authz/administration.py`) precisely
to keep non-human creators out of the cutover grant. The exclusion cannot be
exercised end-to-end without hand-writing the row, so the one branch the flag
exists to produce is the one no CLI test can reach.

Low urgency: the excluded-from-cutover path is covered at the function level in
the existing suite, and non-human creators are created by the importer and model
runners, not by hand.

## Related

Phase H (Task 30) edits this same command to make a duplicate username exit
non-zero instead of printing and exiting 0. That fix was kept separate from this
one on purpose — folding unrelated collateral into a scoped fix is how the
`deploy/` branch acquired its only Critical.
