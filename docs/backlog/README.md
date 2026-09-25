# Backlog

Deferred work, grouped by theme. Each item is a `###` title (imperative or defect) followed by `Status` (open | partial, saying what is left), `Source` (PR, commit or review), `Problem` and `Fix` (1–2 lines each, concrete symbols), and an optional one-line `Note` for a decision or number a fixer must know.
To add: append the item to the fitting file and add a row below. To close: delete the item and its row in the change that fixes it; git is the history.

## Index

| Item | File | Status |
|---|---|---|
| Validate usernames at every entry point | [auth-and-sessions](auth-and-sessions.md) | open |
| Fence `PUBLIC_AUTH_DISABLED` | [auth-and-sessions](auth-and-sessions.md) | open |
| End existing sessions on a password change or reset | [auth-and-sessions](auth-and-sessions.md) | open |
| Stop a token outliving `docker compose down -v` or a restore | [auth-and-sessions](auth-and-sessions.md) | open |
| Make `get_current_user` reject deleted and deactivated accounts | [auth-and-sessions](auth-and-sessions.md) | open |
| Cap the absolute session lifetime | [auth-and-sessions](auth-and-sessions.md) | open |
| Fix or delete the `api_client` branch of `POST /auth/login` | [auth-and-sessions](auth-and-sessions.md) | open |
| Check new passwords against a breached/common-password list | [auth-and-sessions](auth-and-sessions.md) | open |
| Move OIDC login into `AuthService` and pin the auth cookie attributes | [auth-and-sessions](auth-and-sessions.md) | partial |
| Keep admin HTTP writes and reads off non-human Creators | [rbac-admin](rbac-admin.md) | open |
| Rename `has_credential` on `AdminUserResponse` | [rbac-admin](rbac-admin.md) | open |
| Build the audit-log read endpoint `GET /admin/audit` | [rbac-admin](rbac-admin.md) | open |
| Drop the dead `eorm create-user --is-human` option | [rbac-admin](rbac-admin.md) | open |
| Decide the 15 legacy-credential humans the cutover skipped | [rbac-admin](rbac-admin.md) | open |
| Finish trimming `docs/rbac-operations.md` | [rbac-admin](rbac-admin.md) | partial |
| Scope the registration id → `PublicID` lookup in the DTO layer | [rbac-authz](rbac-authz.md) | open |
| Stop `scope.require` passing vacuously for an administrator on nonexistent ids | [rbac-authz](rbac-authz.md) | open |
| Make the session guards fail on stale allow-list entries | [rbac-authz](rbac-authz.md) | open |
| Decide whether `AuthService.change_password` keeps its `actor` parameter | [rbac-authz](rbac-authz.md) | open |
| Decide what `init` does on a schema behind head | [deploy](deploy.md) | open |
| Reach the bundled Keycloak over the compose network | [deploy](deploy.md) | open |
| Refuse the `oidc` layer together with the prod layer | [deploy](deploy.md) | open |
| Build and smoke-test the images CI skips | [deploy](deploy.md) | open |
| Run the upgrade path end to end once | [deploy](deploy.md) | open |
| Tidy the slim-down's stale messages | [deploy](deploy.md) | open |
| Move `orm` (and maybe `server`) to `pyproject.toml` | [deploy](deploy.md) | open |
| Resolve the three GPU worker images in one pip install | [deploy](deploy.md) | open |
| Fix documentation claims that are wrong against the code | [docs](docs.md) | open |
| Move stranded material across the publish boundary | [docs](docs.md) | open |
| Write the missing tutorials and split mixed-mode pages | [docs](docs.md) | open |
| Tidy the deployment pages | [docs](docs.md) | open |
| Stop paying scoped segmentation counts on every app load | [performance](performance.md) | open |
| Check for oversized `IN` lists on `ImageInstance` | [performance](performance.md) | open |
| Size the API pool for multi-hop connection checkout | [performance](performance.md) | open |
| Pick one eager-loading convention and drop dead loads | [performance](performance.md) | open |
| Give the segmentation zarr store a cross-process write lock | [data-integrity](data-integrity.md) | open |
| Add `eorm move-patient` / `move-images` for cross-project data cleaning | [data-integrity](data-integrity.md) | open |
| Make the database the only maintainer of `DateModified` | [data-integrity](data-integrity.md) | open |
| Decide DDL defaults for the `Inactive` columns | [data-integrity](data-integrity.md) | open, low |
| Bump `python-multipart` | [ci-and-tooling](ci-and-tooling.md) | open |
| Clear the npm Dependabot alerts in `client/` and `docs/` | [ci-and-tooling](ci-and-tooling.md) | open |
| Add a backend ruff lint + format gate | [ci-and-tooling](ci-and-tooling.md) | open |
| Make CI checks required on `main`/`development` (coverage Phase C) | [ci-and-tooling](ci-and-tooling.md) | open |
| Add a mypy per-module gate over the admin surface | [ci-and-tooling](ci-and-tooling.md) | open |
| Turn unknown test warnings into errors | [ci-and-tooling](ci-and-tooling.md) | open |
| Repair or delete `eyened_orm.form_validation` | [ci-and-tooling](ci-and-tooling.md) | open |
| Sanitize the `{@html}` cells in `DataTable.svelte` | [frontend](frontend.md) | open |
| Stop treating 403 as an expired session in the API client | [frontend](frontend.md) | open |
| Fix Svelte 5 reactivity traps | [frontend](frontend.md) | open |
| Key the grandfathered `{#each}` blocks | [frontend](frontend.md) | open |
| Ratchet down `@typescript-eslint/no-explicit-any` | [frontend](frontend.md) | open |
| Gate svelte-check in CI (Phase 4) | [frontend](frontend.md) | open |
| Fix the remaining svelte-check error clusters | [frontend](frontend.md) | open |
| Fix the prop bugs unmasked by the `ui/` prop helpers | [frontend](frontend.md) | open |
| Remove small dead code | [frontend](frontend.md) | open |
| Decide `prefer-const` for `.svelte` files | [frontend](frontend.md) | open |
| Re-audit navigation if `kit.paths.base` is ever set | [frontend](frontend.md) | open, conditional |
