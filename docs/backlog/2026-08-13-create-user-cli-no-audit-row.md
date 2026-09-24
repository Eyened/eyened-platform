# `eorm create-user` writes no `AuditLog` row

**Status:** open

## Source

RBAC Phase H whole-branch review, branch `feature/rbac-phase-h-cli`, 2026-08-13.
Phase H promoted `create-user` into the documented `test_user` loop's setup
step (`docs/rbac-operations.md`); that is what surfaced the gap, not a change
to the command itself.

## What

`orm/eyened_orm/cli.py`'s `create_user` command calls
`eyened_orm.utils.db_users.create_user` and commits, but never writes an
`AuditLog` row. Every other `eorm` RBAC command (`grant`, `revoke`,
`set-admin`, `set-password`, `deactivate`, `reactivate`, `init-admin`) calls
`audit_trusted` after its write. `/auth/register` in `server/routes/auth.py`,
the other place a `Creator` gets created, does audit it.

## Why

Creating a principal is the one unattributed action in an otherwise fully
attributed CLI workflow: every state change made *to* an account is on the
audit trail, but the account's own creation is not. Low urgency -- the command
is a trusted path already (see `authz/administration.py`'s module docstring),
and this is a gap in coverage, not a new escalation.

## Related

Not the `--is-human` bug tracked in
[2026-08-13-create-user-cli-is-human-flag.md](2026-08-13-create-user-cli-is-human-flag.md)
-- that is a broken flag on the same command; this is a missing audit row.
Kept as separate notes on purpose.
