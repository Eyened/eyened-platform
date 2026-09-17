# `change_password`'s `actor` argument is informationally redundant today

**Status:** open

## Source

RBAC admin P1 whole-branch review, 2026-09-17.

## What

`change_password` (the route) passes `ActingUser(id=current_user.id,
username=current_user.username)` as `actor`. `AuthService.change_password`
re-derives its subject one line earlier, via `self.authenticate(username,
old_password)`, and that subject is the same `Creator` row as `current_user`
by construction -- a caller can only change their own password. Deriving the
audit actor from the returned `creator` instead of the passed-in `actor`
would produce byte-identical `AuditLog` rows, and would let
`_ACTOR_PARAMETER_ALLOWED` in
`server/tests/test_scope_is_constructor_state.py` be deleted rather than
carry an exemption.

Counter-argument, recorded because it is the reason not to do this today: if
`change_password` ever becomes admin-driven (an administrator resetting
someone else's password), actor and subject legitimately diverge, and the
explicit `actor` parameter is exactly the right shape for that. Removing it
now would have to be re-added later.

Testing consequence worth stating plainly: as long as actor and subject are
always the same row, no test can distinguish "actor taken from the caller"
from "actor taken from the subject" -- the assertion would pass either way.

## Why

Not a bug -- a design trade-off worth recording so it is chosen on purpose
rather than rediscovered. If admin-driven password resets are never built,
the parameter stays permanently unfalsifiable by test and the exemption stays
permanently open.
