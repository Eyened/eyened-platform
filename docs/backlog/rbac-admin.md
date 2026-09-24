# RBAC administration

### Drop the dead `eorm create-user --is-human` option
- **Status:** open
- **Source:** RBAC Phase H, 2026-08-13
- **Problem:** `@click.option("--is-human", is_flag=True, default=True)` in `orm/eyened_orm/cli.py` can never be false, so no non-human Creator can be made from the CLI and `grant_all`'s `IsHuman` exclusion is unreachable end to end.
- **Fix:** remove the option, or implement `--is-human/--not-human` end to end with a test that reaches the `Creator` row. `employee_identifier` is also not exposed by the CLI.

### Write an `AuditLog` row from `eorm create-user`
- **Status:** open
- **Source:** RBAC Phase H review, 2026-08-13
- **Problem:** the `create_user` command in `orm/eyened_orm/cli.py` commits without `audit_trusted`, unlike every other `eorm` RBAC command and `/auth/register`.
- **Fix:** write a `TrustedPath("eorm create-user")` row with `auth:register`'s `changes` shape.
- **Note:** RBAC admin P0 (on `feature/rbac-admin`) fixes this; drop the item when that merges.

### Finish trimming `docs/rbac-operations.md`
- **Status:** partial — cutover moved to the v2026.09.0 upgrade guide, the command reference to `orm/cli.mdx`, and the new-dev checklist rewritten for `deploy/`; the items below remain
- **Source:** merge of `development` into `feature/tasks-page-performance`, 2026-08-21
- **Problem:** its `## Commands` table duplicates `docs/src/content/docs/orm/cli.mdx` and will drift; the `test_user` table predates the multi-project task work.
- **Fix:** delete the Commands table (link to `cli.mdx`), re-check the `test_user` table against current enforcement.
- **Note:** the accepted-risk register left in it is stranded outside the published site; see [docs](docs.md).
