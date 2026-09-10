# `docs/rbac-operations.md` is two documents in one file

**Status:** open

## Source

Found while merging `development` into `feature/tasks-page-performance`,
2026-08-21. The alembic squash (`orm_baseline`) left three revision ids in this
file pointing at migrations that had moved to `versions_archive/`, off alembic's
search path. Those ids are fixed on that branch; the structural problem behind
them is not.

## What

The file is 262 lines holding two documents with different lifecycles:

- **A one-time cutover** (§Cutover, steps 1-5, ~90 lines). Half-executed:
  `grant-all` ran -- `ProjectMember` holds 1,364 rows, 31 creators x 44 projects,
  all `grader` -- while `init-admin` never did, which is why `Creator.IsAdmin` is
  true on **zero rows**. This is the half that rots: it names revision ids,
  container users and one-shot commands.
- **Live reference** (~170 lines): the local-development loop, the 8-scenario
  `test_user` table, the new-dev checklist, a 10-command `eorm` table, and the
  accepted-risks disclosure.

Both halves now have a home that did not exist when the file was written:
`docs/runbooks/` (created 2026-08-20 by
[`2026-08-20-alembic-squash-cutover.md`](../runbooks/2026-08-20-alembic-squash-cutover.md),
which sets the Rules / Steps / Recovery-and-rollback pattern) and the Astro docs
site under `docs/src/content/docs/`.

Suggested split:

| Content | Home |
|---|---|
| Cutover steps 1-5 | `docs/runbooks/`, dated, matching the squash runbook's shape |
| The 10-command `eorm` table | `docs/src/content/docs/orm/cli.mdx` |
| Local-dev loop, joiner flow, `test_user` table | `guides/development_setup.mdx`, `guides/authentication.mdx` |
| Accepted risks | Keep as a doc; it is the only place these are recorded *as accepted risks* rather than as code comments |

## Why

**Nine of the ten RBAC commands are documented only here.**
`docs/src/content/docs/orm/cli.mdx` covers `create-user` and nothing else -- no
`grant`, `revoke`, `init-admin`, `set-admin`, `grant-all`, `grant-for-task`,
`set-password`, `deactivate` or `reactivate`. So the file cannot simply be
deleted, which is the tempting move once its cutover half goes stale.

It is also read in anger, which is how its errors keep surfacing: the RBAC manual
test sweep caught a wrong "no tasks" claim in it, and the 2026-08-21 merge caught
the dead revision ids. A file that is wrong *and* consulted is worse than one that
is merely absent.

The cutover half is what makes this urgent rather than cosmetic. The plan-2
migrations ship under a **scheduled maintenance window with the app fully down**
(decision, 2026-08-21), so an operator will be following this document with the
platform offline -- the worst moment to discover a step naming things that no
longer exist.

## Related

- The runbook must also stop the **importer** and any cron/scripts, not just the
  API. "Bring the app down" does not cover a scheduled importer run, and the
  importer is a third writer.
- Whoever does the split should re-check the `test_user` table against the
  current enforcement behaviour; it predates the multi-project task work.
