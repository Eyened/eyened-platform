# The session guards cannot detect a stale allow-list entry

**Status:** open

## Source

RBAC admin P1 whole-branch review, 2026-09-17.

## What

In `server/tests/test_no_session_in_service_or_route_signatures.py`,
`_offenders` and `_db_access_offenders` skip a function whose `(key_path,
name)` is `in allowed`. That is a one-directional membership test: an
`allowed` entry that matches nothing currently in the codebase is silently
inert and fails nothing. This is unlike `_TRUSTED_CALLERS` in
`server/tests/test_escalation_paths.py`, which asserts the exact set
(`offenders == _TRUSTED_CALLERS`) and therefore ratchets in both directions
-- an unused entry fails just as loudly as an unlisted offender.

Consequence worth stating plainly: this branch closed 12 of the 24
`_SIGNATURE_ALLOWED`/`_DB_ACCESS_ALLOWED` entries the Task 19 guard started
with. Leaving all 24 untouched would have produced an identically green
suite -- the closures were a matter of discipline while writing this branch,
not something the guard itself enforced or would have caught going the other
way.

Fix shape: collect the `(key_path, name)` pairs the scan actually skipped
during a run and assert `set(allowed) <= matched`, so a stale key -- one
naming a function that moved, was renamed, or was deleted -- fails by name
instead of passing vacuously.

Pair this with the second half of the same gap: the untouched entries
(`audit_service.py`'s `__init__`/`_drain`/`_clear`, `get_access_scope`,
`import_single_image`) still lack the "what would remove it" clause that the
entries rewritten on this branch now carry. That prose is currently the only
thing keeping these lists from calcifying into permanent exemptions.

## Why

A guard that cannot fail on a stale or already-vacuous entry provides false
assurance: it looks like enforcement but is, for the untouched half of the
list, only convention.
