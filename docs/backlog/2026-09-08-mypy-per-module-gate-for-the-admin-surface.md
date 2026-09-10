# A mypy per-module gate over the administration surface

**Raised by:** RBAC admin P0 (`docs/superpowers/specs/2026-09-08-rbac-admin-p0-design.md`, P0.11).
**Status:** open, not started.

## Why

`Actor` is a two-variant union whose enforcement is entirely runtime: the
`match` in `AuditWriter.write` raises on an unrecognised variant, and the
guards in `orm/eyened_orm/tests/` check behavior. CI runs no type checker and
the repo has no `[tool.mypy]` section, so nothing checks statically that a
call site passes an `Actor` at all.

**Include `typing.assert_never` in the `case _` when this lands.** The `raise
TypeError` there is the runtime half and catches a value that was never an
`Actor`; it does *not* make a third variant added to the union a static error.
`assert_never` is what does, and it is only worth adding once something checks
it.

`python-type-safety` prescribes per-module overrides as the incremental path,
and P0 leaves a well-bounded surface to point one at: `authz/actor.py`,
`audit_writer.py`, `authz/membership_admin.py`, `authz/account_admin.py`,
`repositories/project_repository.py`.

## Why it was not done in P0

A type gate added *during* a refactor fights the refactor's own churn, and P0
reshapes the surface the gate would check — 524 lines of `Session`-taking
module functions become two repository-holding classes of comparable size
(362 + 159). The win is the shape, not the line count: neither class holds a
`Session`, and `test_no_session_in_service_or_route_signatures.py` now polices
that. Measuring a baseline against the old shape would have measured something
that no longer exists.

## Before starting

**Re-measure; do not assert.** A previous measurement put the true baseline on
`services/` + `repositories/` at 8 errors rather than the 235 a naive run
reports, using `--follow-imports=silent`. That number predates this change and
must be re-taken. Note also that the system `python3` is 3.8 — use
`dev/.venv/bin/python`.
