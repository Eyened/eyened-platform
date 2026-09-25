# Backlog

Deferred work, grouped by theme. Each item is a `###` title (imperative or defect) followed by `Status` (open | partial, saying what is left), `Source` (PR, commit or review), `Problem` and `Fix` (1–2 lines each, concrete symbols), and an optional one-line `Note` for a decision or number a fixer must know.
To add: append the item to the fitting file and add a row below. To close: delete the item and its row in the change that fixes it; git is the history.

## Index

| Item | File | Status |
|---|---|---|
| Stop a token outliving `docker compose down -v` or a restore | [auth-and-sessions](auth-and-sessions.md) | open |
| Fix or delete the `api_client` branch of `POST /auth/login` | [auth-and-sessions](auth-and-sessions.md) | open |
| Move the auth routes behind an `AuthService` | [auth-and-sessions](auth-and-sessions.md) | open |
| Drop the dead `eorm create-user --is-human` option | [rbac-admin](rbac-admin.md) | open |
| Write an `AuditLog` row from `eorm create-user` | [rbac-admin](rbac-admin.md) | open |
| Finish trimming `docs/rbac-operations.md` | [rbac-admin](rbac-admin.md) | partial |
| Scope the registration id → `PublicID` lookup in the DTO layer | [rbac-authz](rbac-authz.md) | open |
| Stop `scope.require` passing vacuously for an administrator on nonexistent ids | [rbac-authz](rbac-authz.md) | open |
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
| Repair or delete `eyened_orm.form_validation` | [ci-and-tooling](ci-and-tooling.md) | open |
| Sanitize the `{@html}` cells in `DataTable.svelte` | [frontend](frontend.md) | open |
| Fix Svelte 5 reactivity traps | [frontend](frontend.md) | open |
| Key the grandfathered `{#each}` blocks | [frontend](frontend.md) | open |
| Ratchet down `@typescript-eslint/no-explicit-any` | [frontend](frontend.md) | open |
| Gate svelte-check in CI (Phase 4) | [frontend](frontend.md) | open |
| Fix the remaining svelte-check error clusters | [frontend](frontend.md) | open |
| Fix the prop bugs unmasked by the `ui/` prop helpers | [frontend](frontend.md) | open |
| Remove small dead code | [frontend](frontend.md) | open |
| Decide `prefer-const` for `.svelte` files | [frontend](frontend.md) | open |
| Re-audit navigation if `kit.paths.base` is ever set | [frontend](frontend.md) | open, conditional |
