# Phase C — make the coverage gates block a merge

**Status:** deferred by design. Phase A (this branch) ships measurement and
advisory checks only.

## What is enforced today

Measured 2026-08-17 against `Eyened/eyened-platform`, not assumed:

- Ruleset **"Protect main and dev branch"** (id 18935463) is `enforcement: active`
  and targets both `refs/heads/main` and `refs/heads/development`.
- Its rules are `deletion`, `non_fast_forward`, and `pull_request` — the last
  requiring 1 approving review with `require_code_owner_review: true`.
  `.github/CODEOWNERS` assigns every path to `@Eyened/platform-core`.
- There is **no `required_status_checks` rule** on either branch.

So merges are already gated — on human review. What no rule gates is a *check*.
Phase C is narrower than "turn enforcement on": it adds `required_status_checks`
to an existing, already-active ruleset.

## Open questions, to be answered with real PR data rather than in advance

1. **Which of the three checks become required?** `Server CI / test`,
   `Client CI / client`, `Client CI / coverage`. The client job split makes
   requiring `client` without `coverage` a real option, which matters on a tree
   with 17 test files where most frontend PRs will go red at first.
2. **The legitimate-exception case.** A refactor that deletes code and its tests
   together can miss the floor for a good reason. Python has no way to fail
   coverage independently of tests, so an exception mechanism is a phase C
   question, not something to solve with an escape hatch now.
3. **Are admin rights on `Eyened/eyened-platform` held?** Editing a ruleset needs
   them. Reading one does not, and reading is all that was done here — so this
   remains unconfirmed.

## Known blind spots — weigh these before making anything required

Both were found in the branch's final review, and both are *unguarded* by choice.
An advisory gate that under-measures is merely optimistic; a required one that
under-measures is a false assurance, so settle these first.

1. **`[tool.coverage.run] source` must stay rooted at `orm`, not `orm/eyened_orm`.**
   Narrowing it makes `server/db.py` and `orm/eyened_orm/db.py` both serialize as
   `db.py`; one is dropped and diff-cover serves the survivor's coverage for both
   paths. Measured: an uncovered change to `orm/eyened_orm/db.py` passed the gate
   with "No lines with coverage information in this diff". A new top-level
   `orm/db.py` or `orm/config.py` would collide the same way. `pyproject.toml`
   carries a warning comment; nothing enforces it, and the full suite stays green
   either way.
2. **A directory without `__init__.py` is invisible to the Python gate.** Coverage
   prunes such subdirectories of a `source` root, so their files never reach
   `coverage.xml` and diff-cover skips them. `import_utils/__init__.py` was added
   for exactly this reason, but the next such directory will be invisible again.
   The client side does not share this weakness — `vite.config.ts` uses `include`
   so never-imported files appear at 0% — so the two gates disagree on their
   central anti-vacuity property.

Either could be enforced with a test in `server/tests/test_coverage_omissions.py`,
which already guards the omit list in three directions. `include_namespace_packages`
would fix (2) but admits 24 never-executed alembic files and reddens every
migration PR.

Prerequisite: several weeks of advisory runs, so the 80% figure is known to be
achievable on this codebase before it starts blocking anyone.
