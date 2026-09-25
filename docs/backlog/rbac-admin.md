# RBAC administration

### Keep admin HTTP writes and reads off non-human Creators
- **Status:** open
- **Source:** RBAC admin P3b review (2026-09-22) + PR #247 review (2026-09-24)
- **Problem:** `_creator_by_id` in `orm/eyened_orm/authz/account_admin.py` and `authz/membership_admin.py` is a bare `session.get(Creator, id)`. So `PUT /admin/users/{id}/password|active`, `PUT/DELETE /admin/projects/{p}/members/{id}` and `GET /admin/users/{id}/memberships` all accept `IsHuman=False` Creators that the `/admin/users` roster (`CreatorRepository.list_humans()`) never lists; an AI-model Creator can be given a working password.
- **Fix:** filter `IsHuman` in `AdminService` (404 on the HTTP path), not in `_creator_by_id`, so the CLI trusted path keeps its wider reach.

### Rename `has_credential` on `AdminUserResponse`
- **Status:** open
- **Source:** PR #247 review, 2026-09-24; behaviour from `18b8b2da`
- **Problem:** `has_credential` (`server/routes/admin.py`) is `has_password(creator) or creator.Password is not None` — "has a usable password" — reversing P2 spec D2; OIDC accounts now report `false`.
- **Fix:** rename to `has_password`, or document the meaning on the DTO, before the client consumes it.

### Build the audit-log read endpoint `GET /admin/audit`
- **Status:** open
- **Source:** RBAC admin parent spec D3; deferred by P2 to its own spec ("P2b"), after P3b
- **Problem:** CLI backdoor rows (`TrustedPath` actors) must be visible in the admin UI; there is no read endpoint. Blocks the admin UI's audit view.
- **Fix:** specify and build P2b.

### Drop the dead `eorm create-user --is-human` option
- **Status:** open
- **Source:** RBAC Phase H (2026-08-13) + PR #247 review (2026-09-24)
- **Problem:** `@click.option("--is-human", is_flag=True, default=True)` in `orm/eyened_orm/cli.py` can never be false, and `create_user` ignores it anyway (`AccountAdministration.create` makes only human accounts).
- **Fix:** remove the option, or implement `--is-human/--not-human` end to end with a test that reaches the `Creator` row. `employee_identifier` is also not exposed by the CLI.

### Decide the 15 legacy-credential humans the cutover skipped
- **Status:** open (data decision, not code)
- **Source:** found while specifying P2 `has_credential`, 2026-09-17
- **Problem:** `grant_all` drives off `CreatorRepository.list_authenticatable` (`PasswordHash IS NOT NULL`); 15 active, non-admin humans with only legacy `Creator.Password` can log in but hold zero memberships, so see nothing. Ten have 13,582 annotations; "Graders" is a shared account.
- **Fix:** per account, grant (still grading), leave/deactivate (dormant), or remove (shared login). `GET /admin/users` rows with `has_credential: true` and no memberships are exactly this set.

### Finish trimming `docs/rbac-operations.md`
- **Status:** partial — cutover moved to the v2026.09.0 upgrade guide, the command reference to `orm/cli.mdx`, and the new-dev checklist rewritten for `deploy/`; the items below remain
- **Source:** merge of `development` into `feature/tasks-page-performance`, 2026-08-21
- **Problem:** its `## Commands` table duplicates `docs/src/content/docs/orm/cli.mdx` and will drift; the `test_user` table predates the multi-project task work.
- **Fix:** delete the Commands table (link to `cli.mdx`), re-check the `test_user` table against current enforcement.
- **Note:** the accepted-risk register left in it is stranded outside the published site; see [docs](docs.md).
