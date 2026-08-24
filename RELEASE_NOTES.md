# EyeNED Platform v2026.07.0

Major release: OpenID Connect login, a renewed ORM importer, centralized thumbnail generation, unified `eorm` CLI targeting, registration model versioning, major viewer and segmentation improvements, ETDRS/form-schema tooling, and refreshed deployment documentation.

## Highlights

- **OpenID Connect authentication** — optional SSO with secure ID-token validation, nonce/CSRF checks, optional automatic account creation, and a local Keycloak setup for development.
- **Renewed ORM importer** — plans changes before applying them, supports CSV input, JSON audit/undo files, idempotent re-runs, and clearer matching of patient/study/series/image records. Clearer errors when required parent records cannot be resolved.
- **Unified `eorm` CLI targeting** — shared `--path`, `--project`, `--patient`, `--exclude`, and `--modality` flags across inference and maintenance commands (`run-models`, `run-segmentation`, `run-registration`, `run-etdrs-model`, `update-thumbnails`, `update-hashes`).
- **Registration model versioning** — each package version gets its own `Model` row; patient attributes preserve provenance per model version; viewer crosshair linking works across registration graph versions.
- **Centralized thumbnail generation** — use `eorm update-thumbnails`, importer `PostImport`, or async API jobs backed by an RQ worker.
- **Segmentation and measurement improvements** — unified creation flows, region tools, feature pipette support, multiclass/multilabel opacity controls, B-scan link scrolling, probability-mask area calculation fixes, and clearer overlay rendering.
- **ETDRS and form schemas** — builtin viewer FormSchemas can be seeded with `eorm seed-form-schemas`; new ETDRS panel and Form Schema documentation.
- **Viewer UX** — embeddable browser widget in the viewer and task UI, global help panel, per-panel help overlays, browser overlay fixes, and smoother task/search performance.
- **Database setup** — `eorm initialize-database` now stamps the current Alembic revision; fresh installs should also run `eorm seed-form-schemas`.
- **Deployment and developer setup** — updated Docker, database, Redis/RQ worker, Keycloak, and storage docs; database dumps split into the `database/` stack.

## Bug fixes

- Segmentations now load when adding images dynamically to the viewer.
- Browser overlay correctly shows loaded images.
- ETDRS overlay renders correctly on enface OCT images.
- pyjwt dependency bump fixes an import error with `AllowedRSAKeys`.

## Upgrade notes

1. **Run database migrations** before starting the new server containers.
2. **Seed builtin form schemas** on new deployments: `eorm seed-form-schemas` (or `eorm initialize-database --seed-form-schemas`).
3. **Review authentication settings** before deployment. Password login remains enabled by default; OIDC is opt-in via `EYENED_API_AUTH_OIDC_ENABLED=true`.
4. **Ensure an RQ worker** listens to the `default` queue if you use async thumbnail jobs.
5. **Reinstall `eyened_orm`** after pulling this release so ORM-owned dependencies (including `zarr`) are current.
6. **Patient attributes API change:** `GET /patients/{id}` now returns each attribute as a list of `{ value, model }` entries so provenance per model version is preserved.

## Documentation

- [Release notes](https://eyened.github.io/eyened-platform/release_notes/)
- [Getting started](https://eyened.github.io/eyened-platform/getting_started/)
- [Authentication](https://eyened.github.io/eyened-platform/guides/authentication/)
- [Importing data](https://eyened.github.io/eyened-platform/importing_data/)
- [ETDRS panel](https://eyened.github.io/eyened-platform/client/etdrs_panel/)
- [Form schemas](https://eyened.github.io/eyened-platform/orm/form_schemas/)
