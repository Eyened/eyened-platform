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

Prerequisite: several weeks of advisory runs, so the 80% figure is known to be
achievable on this codebase before it starts blocking anyone.
