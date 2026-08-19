# EyeNED Platform v2026.08.0

Viewer bookmarks and enface overlays, a service/repository layer with an append-only audit log (RBAC prep), a CFI inference rewrite, CI on client and server, and several viewer/ORM reliability fixes.

## Highlights

- **Viewer view-state** — open main viewers and frame indices persist in the URL (`v=`) and localStorage, and restore after reload (#198).
- **Enface overlays on registered images** — GPU registration hops map enface projections onto linked images; photolocator hit-specs cover raster, radial, and circular locators (#177, #194).
- **Pre-RBAC server architecture** — routes go through repositories and services; mutations write an in-transaction `AuditLog`; session ownership is explicit (#134, #139, #145, #165, #171). Per-request authorization is not enabled yet.
- **CFI inference rewrite** — `eorm run-cfi-models` with ModelInputSpec, automatic model versions, failure tracking, streaming/chunked targets, and deadlock retry (#158).
- **CI** — client Vitest/build/Prettier/ESLint and server pytest run on push/PR into `development` and `main`.
- **CODEOWNERS** — repository-wide review by `@Eyened/platform-core`.

## Bug fixes

- Oversized DICOM volumes and enface/OCT stretch (#196 / #173).
- Patient registration on the task viewer route (#144).
- CirclePhotoLocator viewer crash (#157).
- Multiclass erode/dilate (#131).
- PNG series path resolution defaults to index 0 (#191).
- Copy image public ID from browser and viewer (#140, #143).
- Unused `mysql-connector-python` removed (#199).
- Registration processing exception handling (#147).

## Upgrade notes

1. **Run database migrations** before starting the new server containers. This release adds `AuditLog`.
2. **Reinstall `eyened_orm`** after pulling this release.
3. Prefer **`eorm run-cfi-models`**; legacy CFI inference writers were removed.
4. Do not depend on **`mysql-connector-python`**.
5. Authentication (password + optional OIDC) is unchanged from v2026.07.0.

## Documentation

- [Release notes](https://eyened.github.io/eyened-platform/release_notes/)
- [Getting started](https://eyened.github.io/eyened-platform/getting_started/)
- [CFI / inference](https://eyened.github.io/eyened-platform/orm/inference/)
- [Attributes](https://eyened.github.io/eyened-platform/orm/data_model/attributes/)
