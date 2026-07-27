# Design: Consolidate app bootstrapping into one `deploy/` directory

Date: 2026-07-24 (extended 2026-07-27)
Status: Design approved. Landing strategy deliberately deferred until a prototype exists (see "Landing plan").

## Context / Problem

Everything needed to run the platform is scattered across **four+ Docker stacks**, each with its own env files:

| Location | Runs | Env files |
|---|---|---|
| `database/` | MySQL + adminer (+ xtrabackup) | `.env`, `.env.example` |
| `dev/` | redis + nginx + server + client (hot-reload) | `.env`, `.env.alembic`, `sample.env` |
| `docker/` | redis + server + client + nginx (prod) | `.env.example` |
| `worker/` | 4 GPU inference workers | `.env.example` |

Consequences:

- **`dev/` and `docker/` are ~80% duplicated.** `Dockerfile.server` differs only in a trailing `CMD` (and the prod file's first `CMD` is dead — Docker keeps only the last); `nginx.conf` differs only in the client upstream port (5173 vs 4173); `Dockerfile.client` differs only dev-vs-prod. Editing one silently drifts from the other.
- **Env vars are duplicated and inconsistently named** across 6 files (`PORT` vs `DEV_NGINX_PORT`, `MYSQL_*` vs `EYENED_DATABASE_*`, `root` vs `eyened` creds). A newcomer can't tell which `.env` feeds what.
- **The database is a separate stack** reached over `host.docker.internal`, so even locally it's two `docker compose up`s in two directories.
- **Per-developer isolation is done with a gitignored, hardcoded compose file** (`dev/docker-compose.yml`, project name `…-kaustav`) plus real secrets in an untracked `dev/.env.alembic`. The isolation itself is a **required capability** — multiple developers share one powerful host and must not collide — but baking one person's name into an uncommittable file means every new dev hand-rolls their own.
- **Storage configuration is scattered across three places that must agree** (see below), with no single source of truth — and two of the three are currently wrong.

## Goals

1. **Great developer experience** — hot reload out of the box, one `.env` driving everything, no personal gitignored compose files.
2. **Very easy setup for even non-technical users** — install Docker, run one command, get the whole platform *including the database*, with working defaults and no manual editing on the happy path.
3. **Handle multi-client deployments and debugging later** — one shared base with prod/per-client layers; external/managed DB one setting away; multiple isolated stacks on one host.

## Findings that shaped this design

Established by reading the code and probing the running dev stack on 2026-07-27.

### Storage is two independent layers

Per bart's (unmerged) `origin/docs/clarify-storage-mounts-151`, which answers open issue #151:

- **Platform storage** (`EYENED_STORAGE_ROOT`, default `/storage`) — writable data the platform owns: `thumbnails/` and `segmentations.zarr`.
- **Image datasets** (`EYENED_STORAGE_MOUNTS`) — read access to original image files. A JSON map `{StorageBackend.Key: local path}` parsed at `orm/eyened_orm/data_access.py:66-75`. Optional in principle: only hosts where **Python** reads source images from disk need it. The browser never does.

Images are not in MySQL. `ImageStorage.ObjectKey` + `StorageBackend.Key` (`orm/eyened_orm/image_instance.py:93`) point into a backend. The live dev database has three backends: `oogergo` (1,819,935 objects, `/mnt/oogergo`), `genr` (25,241, `/mnt/genr`), and `thumbnails` (0 objects — vestigial; `resolve_thumbnail_ref` hardcodes that key at `storage_access.py:69` and resolves it under `EYENED_STORAGE_ROOT`).

Serving is zero-copy: the API returns an empty response with `X-Accel-Redirect: /{key}/{relative_path}` (`storage_access.py:13`, `server/routes/instances.py:100`); nginx matches an `internal` `location /{key}/`, `alias`es it, and sendfiles the bytes.

So **each backend key costs three edits today** — a compose bind mount, an nginx `location`, and an `EYENED_STORAGE_MOUNTS` entry — with a fourth source of truth (the `StorageBackend` rows) outside the repo. `docker/nginx.conf` even ships a comment stub instructing operators to hand-add a location per backend.

### Two live configuration bugs

1. **In-process image reads are broken.** `EYENED_STORAGE_MOUNTS` is set in no env file, and neither is `EYENED_API_URL`. Verified inside the running server container: `is_local_storage_enabled()` → `False` → `ApiDataAccessAdapter` → `get_api_client()` raises `ValidationError: url missing, username missing` (`api_client.py:14`, `config.py:27-30`). Every Python-side pixel read therefore fails — `image_instance.py:451/480/503/518/542` (`pixel_array`, mhd and png_series loaders), `segmentation.py:178/235` — which takes out thumbnail regeneration, inference, and reports. It went unnoticed because the browser path never executes it.
2. **`EYENED_API_USER` is silently ignored.** The settings field is `username` under prefix `EYENED_API_`, so the correct name is `EYENED_API_USERNAME`. `dev/.env` sets `EYENED_API_USER`; the password is picked up, the username is not.

Giving the server container `EYENED_STORAGE_MOUNTS` fixes (1) outright: it selects `LocalDataAccessAdapter`, so no API URL, no credentials, and no server calling its own HTTP API for bytes it could read directly.

### Migrations cannot run unattended

`orm/migrations/alembic/env.py:56-65` calls bare `input()` for any command outside `{revision, history, current, heads, branches, show, check, list_templates, stamp}` — `upgrade` prompts. There is no `-x` flag, env var, or TTY check, so any non-interactive invocation dies.

### Dev writes into production storage

`dev/.env:12` sets `EYENED_STORAGE_ROOT=/mnt/oogergo/eyened/eyened_platform`, which puts `segmentations.zarr` (`segmentation_storage.py:13-17`) in the **production** store, mounted read-write — carrying an in-tree TODO and issue #119. Whatever `deploy/.env.example` ships becomes every future developer's default, so this is a decision rather than a detail.

## Decisions

1. One command brings up **everything including a bundled MySQL**; external DB is an `.env` toggle.
2. Scope of the unified stack = `database` + `redis` + `server` + `client` + `fileserver` (dev **and** prod). Keycloak folds in as an optional `oidc` profile. Workers stay a separate deployment, only env-name-aligned.
3. Location = a single new top-level **`deploy/`** directory, driven by a thin root `Makefile`.
4. Per-dev isolation = `COMPOSE_PROJECT_NAME` in each dev's **own untracked `.env`** (no gitignored personal compose, no name baked into shared files).
5. Default dev database = **bundled MySQL per dev** (own container + volume); external DB one setting away.
6. **Storage mounts have one source of truth**: `deploy/storage-mounts.json` (untracked; `.example` committed). A generator derives all three consumers from it. Backends are mounted at the same path inside the container as on the host, so one path per key suffices.
7. **The server container gets `EYENED_STORAGE_MOUNTS`**, making local reads the default path and retiring the self-API fallback.
8. **The env-schema bugs are fixed here** — `EYENED_STORAGE_MOUNTS` and `EYENED_API_URL` added, `EYENED_API_USER` → `EYENED_API_USERNAME`, worker names aligned.
9. **`EYENED_STORAGE_ROOT` is always `/storage` inside the container**, backed by a named volume by default. Pointing at shared or production storage is an explicit opt-in line in the untracked `.env`.
10. **`make up` bootstraps an empty database** (migrate, seed, create admin) so goal 2 is literally one command.
11. **Migrations are container-only.** `dev/.env.alembic` disappears; host access to MySQL is opt-in, not default.

## Design

### Target layout

```
deploy/
  compose.yaml                # base: all services; local-db + oidc profiles; prod-ready defaults
  compose.override.yaml       # dev layer (auto-applied by bare `docker compose up`)
  compose.prod.yaml           # prod/deploy layer (explicit -f; excludes dev override)
  compose.storage.yaml        # GENERATED from storage-mounts.json (gitignored)
  Dockerfile.server           # unified (one build; run command set per env in compose)
  Dockerfile.client           # multi-stage: shared base -> `dev` and `prod` targets
  nginx/
    default.conf.template     # base proxy + thumbnails; client port via ${CLIENT_UPSTREAM_PORT}
    conf.d/storage.conf       # GENERATED per-backend `location` blocks (gitignored)
  entrypoint-client.sh        # moved from dev/
  keycloak/                   # moved from dev/keycloak/ (realm template + entrypoint)
  scripts/
    gen-storage.sh            # storage-mounts.json -> compose overlay + nginx conf + env var
    bootstrap.sh              # first-run: migrate + seed + admin user (idempotent)
    load_dump.sh              # moved from database/, compose paths updated
    save_dump.sh              # moved from database/
  storage-mounts.json.example # committed template
  .env.example                # single committed template (working local defaults)
  README.md                   # the one bootstrap doc
Makefile                      # (root) up/down/logs/prod/reset/migrate/db-snapshot + first-run .env creation
.dockerignore                 # (root) trim the `context: ..` build context
```

Per-client deploys add `deploy/compose.<client>.yaml` + `deploy/.env.<client>` (gitignored), layered on `compose.prod.yaml`.

### Compose layering — one base serves dev + prod + clients

- **`compose.yaml` (base)** — the shared service graph and prod-ready defaults: `database` + `adminer` under a `local-db` profile; `redis`; `server` (build `Dockerfile.server`, default = prod `gunicorn` CMD, healthcheck); `client` (build target `prod`); `fileserver` (nginx, template mounted, default `CLIENT_UPSTREAM_PORT=4173`). `keycloak` under an `oidc` profile. Named volumes `db_data`, `platform_storage`, `client_node_modules`. **No hardcoded `name:`** — the project name comes from `COMPOSE_PROJECT_NAME`. **Pin all images** (`nginx:1.27-alpine`, `adminer:4.8.1`, `redis:7-alpine`, `mysql:8.0.27`) — no `latest`. The `database` service carries a **healthcheck** (`mysqladmin ping`, ~5s interval / 10 retries).
- **`compose.override.yaml` (dev, auto-applied)** — dev refinements only: `client` build target `dev` with `CLIENT_UPSTREAM_PORT=5173`; `server` `command:` → `uvicorn --reload` plus source bind mounts (`../server`, `../orm`); `client` node_modules volume + `../client` bind mount. This layer owns **`server depends_on database: condition: service_healthy`** (see below) and modest **resource limits** (`mem_limit`/CPU) on `database`/`server` — important because many devs share one host. `deploy/.env.example` ships `COMPOSE_PROFILES=local-db`.
- **`compose.prod.yaml` (prod/deploy)** — prod-only concerns not already in the base (`restart:` policies, `deploy.resources` limits, external-DB expectations). Run with `docker compose -f compose.yaml -f compose.prod.yaml up`, which does **not** auto-load the dev override.
- **`compose.storage.yaml` (generated)** — dataset bind mounts only. Included via `COMPOSE_FILE` in `.env` so bare `docker compose up` still works.

**Startup ordering & the external-DB toggle (correctness):** the `server → database` `depends_on` must live **only** in the `local-db` context (the dev override, or a small `compose.local-db.yaml` layered with the profile), **never in the base**. If an always-on `server` in the base declared `depends_on: database` while `database` is gated behind `profiles: [local-db]`, then turning the profile off (external DB) would make Compose refuse to start — it cannot depend on a disabled service. Keeping the dependency in the local-db layer means: bundled DB → server waits for MySQL to be healthy (no first-run crash-loop); external DB → no `database` service, no dangling dependency.

Behavior: **bare `docker compose up` = dev** (base + auto override → bundled DB + hot reload); **explicit `-f` list = prod/client** (base + prod [+ client] → external DB).

### Storage configuration — one file, three derived artifacts

`deploy/storage-mounts.json` (untracked, `.example` committed) is the single source of truth:

```json
{
  "oogergo": "/mnt/oogergo",
  "genr": "/mnt/genr"
}
```

`deploy/scripts/gen-storage.sh`, run by `make up`, emits:

1. `EYENED_STORAGE_MOUNTS` (compact JSON) into the `server` and worker environments — Python reads files locally, no API round-trip.
2. `deploy/compose.storage.yaml` — one `- <path>:<path>:ro` bind mount per key, on `fileserver` and `server`.
3. `deploy/nginx/conf.d/storage.conf` — one `location /<key>/ { internal; alias <path>/; }` per key, `include`d by the base template.

Both generated files are gitignored. An empty or absent `storage-mounts.json` produces empty artifacts, which is exactly right for a clean clone: a fresh bundled database has **no `StorageBackend` rows** (`eorm initialize-database` creates none), so a newcomer configures no mounts at all. Mount configuration is a property of the database you attach to, which is why it must not live in a committed shared file.

Because keys must match `StorageBackend.Key`, a separate `make check-storage` target reports configured keys with no matching row and rows with no configured mount. It is deliberately *not* part of `make up`: generation must work before any database exists.

**Platform storage** is separate and simple: `EYENED_STORAGE_ROOT=/storage` always inside the container. By default `/storage` is the named volume `platform_storage`, so a clean clone writes nothing outside its own stack and never touches the production zarr. Attaching to shared storage is one explicit line in the untracked `.env`:

```bash
# Opt in to shared/production platform storage (thumbnails + segmentations.zarr).
# Leave unset to use this stack's own volume.
PLATFORM_STORAGE_PATH=/mnt/oogergo/eyened/eyened_platform
```

### Unifying the duplicated pieces

- **`Dockerfile.server`** → one file. Build steps are already identical; only the run command differs, and it moves to compose (`gunicorn` in base, `uvicorn --reload` in dev override). The prod file's dead second `CMD` disappears.
- **`Dockerfile.client`** → one multi-stage file: shared base (node, copy client, `npm install`), a `dev` target (entrypoint, hot-reload on 5173), a `prod` target (`npm run build` + preview on 4173). Compose selects the target per environment.
- **`nginx`** → one `default.conf.template`; the client upstream port becomes `${CLIENT_UPSTREAM_PORT}` (nginx already substitutes env vars in `*.template`). The per-backend `location` blocks are generated (above), replacing both dev's hand-edited `/oogergo/` + `/genr/` blocks and prod's "add a location per StorageBackend" comment stub.
- **Non-root prod (hardening, not blocking):** the `prod` targets should add a non-root `USER`. The `dev` stage stays root for bind-mount write convenience.

### Single env schema (`deploy/.env.example`)

One committed template with **working local defaults** (dev-only passwords, clearly marked not-for-prod) so `make up` from a clean clone works with zero editing on a solo machine. Names are consolidated onto the canonical `EYENED_*` set (per `docs/src/content/docs/orm/configuration.mdx`). Sections:

- **Per-developer isolation (shared host):** `COMPOSE_PROJECT_NAME=eyened` (comment: set to `eyened-<yourname>` on the shared server) and `HTTP_PORT` / `ADMINER_PORT` (comment: pick unique per dev). Renamed from `DEV_NGINX_PORT` because the same variable serves prod; `DEV_PUBLIC_HOST` becomes `PUBLIC_HOST` for the same reason. Both are consumed by the Keycloak compose service and `keycloak/entrypoint.sh` (OIDC redirect + web origin), which move under `deploy/` and get updated with them.
- **Database:** bundled defaults; `DB_PUBLISH_PORT` present but **commented out** — the server reaches MySQL in-network at `database:3306`, so no host port is published by default (the biggest source of cross-dev collisions). A dev who wants DBeaver or a host-side alembic uncomments it and picks a unique value. A commented block shows how to point at an external DB instead.
- **Storage:** `PLATFORM_STORAGE_PATH` (commented out; defaults to the named volume). `EYENED_STORAGE_MOUNTS` is *not* hand-written here — it is generated from `storage-mounts.json`.
- **API:** `EYENED_API_SECRET_KEY`, plus correctly-named `EYENED_API_URL` / `EYENED_API_USERNAME` / `EYENED_API_PASSWORD` (only needed by hosts without mounts — notebooks, remote workers), with a comment saying so.
- **Profiles:** `COMPOSE_PROFILES=local-db` (add `oidc` to enable Keycloak).
- **Secrets:** real values only ever in the untracked `.env` / `.env.<client>`.

### Root `Makefile` wrapper (goal 2: one command)

- `make up` — first run copies `deploy/.env.example` → `deploy/.env` and `storage-mounts.json.example` → `storage-mounts.json` if missing (printing the "personalize `COMPOSE_PROJECT_NAME` + `HTTP_PORT` on a shared host" note); runs `gen-storage.sh`; brings the dev stack up `-d --build`; then runs `bootstrap.sh` and prints the login URL.
- `make down`, `make logs`, `make reset` (down + volumes), `make prod` (the `-f compose.yaml -f compose.prod.yaml` invocation), `make migrate` (alembic inside the server container), `make db-shell`.
- `make db-snapshot NAME=…` / `make db-restore NAME=…` — cold tar of the MySQL data volume, container and volume names derived from `COMPOSE_PROJECT_NAME`. This generalizes the currently hand-written procedure in `plan.md`, whose commands hardcode one developer's container name. The safety net matters because MySQL auto-commits DDL per statement, so a half-applied migration cannot be reliably undone with `alembic downgrade`.
- Keep the existing `gen-openapi` / `gen-types` targets.

### First-run bootstrap (`deploy/scripts/bootstrap.sh`)

Idempotent, and safe to skip when the database is already populated:

1. Wait for the `database` healthcheck (already declared).
2. If `alembic current` is empty → `alembic upgrade head`; otherwise report the current revision and do nothing.
3. `eorm seed-form-schemas`.
4. If no accounts exist → create the admin from `.env` credentials; otherwise skip.

Step 2 needs a non-interactive path past the confirmation prompt at `env.py:56-65`. Add an explicit opt-out — `-x assume_yes=1` (or `ALEMBIC_ASSUME_YES=1`) — and keep prompting by default, so the safety rail stays for humans while automation can pass it deliberately. This touches migration tooling, not application or business logic, and is the only code change in this design.

### Migrations & DB init (reuse existing tooling)

Drop `dev/.env.alembic`. Migrations and init run **inside the server container**, which already has the unified env loaded and ships `/app/orm/migrations/` plus the `eorm` CLI via `pip install -e /app/orm`:

- `make migrate` → `docker compose exec -it server alembic -c orm/migrations/alembic.ini upgrade head` (interactive, so the confirmation prompt still guards manual runs).
- `docker compose exec server eorm initialize-database` / `eorm seed-form-schemas` / `eorm create-user`.
- Data dumps via `deploy/scripts/{load,save}_dump.sh` and/or `eorm load-dump` / `save-dump`.

Host-side alembic remains possible for anyone who uncomments `DB_PUBLISH_PORT`, but it is no longer the documented path.

### Keycloak (optional `oidc` profile)

Fold `dev/keycloak/docker-compose.keycloak.yml` into `compose.yaml` as a service gated by `profiles: [oidc]`; keep `realm-eyened-dev.json.template` + `entrypoint.sh` under `deploy/keycloak/`, updated for `PUBLIC_HOST` / `HTTP_PORT`. Off by default so "clone and run" stays lean.

### Workers (env-aligned only)

Leave `worker/` as its own deployment. Reconcile `worker/.env.example` with the canonical set and **add `EYENED_STORAGE_MOUNTS`**, which inference and thumbnail generation need (`docs/src/content/docs/thumbnails.mdx:158`) and which the template currently omits.

## Landing plan

The prototype comes before the cutover decision. `dev/`, `docker/`, and `database/` are almost entirely bart's work, and four contributors are active with branches in flight, so the disruption is worth measuring rather than guessing.

1. Build `deploy/` on `feature/deploy-consolidation` (worktree `../eyened-platform-worktrees/deploy-consolidation`, branched from `origin/development`).
2. Verify it two ways: a clean clone with the bundled DB, and this shared host attached to the existing dev database and datasets.
3. **Then** choose how to land it — additive with `dev/`/`docker/`/`database/` marked deprecated and deleted in a follow-up PR, or a single PR that adds and deletes with an `adopt-env` helper — with evidence about what actually breaks.

Related in-flight work to reconcile before merging: open issue #151 and bart's unmerged `origin/docs/clarify-storage-mounts-151`, whose two-layer framing this design adopts.

## File-level impact

**Create:** `deploy/compose.yaml`, `deploy/compose.override.yaml`, `deploy/compose.prod.yaml`, `deploy/Dockerfile.server`, `deploy/Dockerfile.client`, `deploy/nginx/default.conf.template`, `deploy/scripts/gen-storage.sh`, `deploy/scripts/bootstrap.sh`, `deploy/storage-mounts.json.example`, `deploy/.env.example`, `deploy/README.md`, root `Makefile` targets, root `.dockerignore`.

**Move (with path fixes):** `dev/entrypoint-client.sh`, `dev/keycloak/*`, `database/load_dump.sh`, `database/save_dump.sh` → under `deploy/`.

**Modify (code):** `orm/migrations/alembic/env.py` — non-interactive opt-out for the confirmation prompt.

**Delete (superseded, timing per the landing plan):** `dev/docker-compose.yml`, `dev/Dockerfile.server`, `dev/Dockerfile.client`, `dev/nginx.conf`, `dev/.env`, `dev/.env.alembic`, `dev/sample.env`, `docker/*`, `database/docker-compose.yaml`, `database/.env`, `database/.env.example`. Merge useful prose from `dev/README.md`, `docker/README.md`, `database/README.md` into `deploy/README.md`. (`dev/generate_openapi.py` is dev tooling, not env/docker — leave it.)

**Update:** root `.gitignore` (remove `dev/docker-compose.yml`, `docker/.env`; add `deploy/.env`, `deploy/.env.*` with `!deploy/.env.example`, `deploy/storage-mounts.json`, `deploy/compose.storage.yaml`, `deploy/nginx/conf.d/storage.conf`); root `README.md` "Repository overview"; `worker/.env.example`.

**Reuse (do not reinvent):** nginx `*.template` env substitution; the `server` healthcheck + `adminer`/`xtrabackup` profile patterns; `eorm initialize-database` / `seed-form-schemas` / `create-user` / `load-dump` / `save-dump`; the `EYENED_*` schema in `docs/src/content/docs/orm/configuration.mdx`.

## Out of scope

- Pulling `worker/` GPU stacks into the unified compose (they deploy to separate GPU hosts).
- Application/business-logic code changes. (The `env.py` prompt opt-out is migration tooling and is the sole exception.)
- Fixing the underlying zarr concurrency issues, issue #119 (tracked separately). This design reduces exposure by defaulting new stacks away from the production store, but does not fix the store.

## Future / deferred hardening

- **Registry-based images + image scanning.** Prod/multi-client currently builds images on each host (non-reproducible, unscanned). Forward path: CI builds, `trivy`-scans, and pushes tagged images to GHCR, with `compose.prod.yaml` referencing the pinned tag instead of `build:`.
- **Secrets management for prod.** Per-client secrets in `.env.<client>` should graduate to Compose `secrets:` or an external manager.
- **Non-root prod containers** — cheap to add to the Dockerfile prod stages when the prod layer is first exercised.
- **Deriving mounts from the database.** Issue #151 asks why operators maintain a key→path map at all. `StorageBackend.Config` (a JSON column, currently an unused placeholder) could carry a default path, letting the generator read the DB. Deferred: it inverts the bootstrap order (nginx config would depend on a running database) and physical paths differ per deployment, which is exactly what env config is for.

## Verification

1. **Clean-clone dev bring-up (goals 1+2):** from a fresh checkout, `make up` → the server waits for MySQL to report healthy, migrations apply, form schemas seed, an admin is created, and the UI loads at `http://<host>:${HTTP_PORT}` with `/api/health` responding. Nothing stuck in `restarting`. No manual editing on a solo machine, and no dataset mounts configured.
2. **Idempotence:** a second `make up` on the populated stack re-runs bootstrap harmlessly — no duplicate admin, no migration attempt, no error.
3. **The in-process read bug is actually fixed:** in the server container, `image.pixel_array` on a real image returns data instead of raising `ValidationError`. This is the regression proof for the two env bugs.
4. **Generated artifacts match their source:** `compose.storage.yaml` and `nginx/conf.d/storage.conf` contain exactly the keys in `storage-mounts.json`; an image request served through nginx via X-Accel resolves from the right mount.
5. **Hot reload (goal 1):** edit a `server/` file and a `client/` file → server reloads and Vite HMR updates without a rebuild.
6. **Multi-dev isolation (the `-kaustav` requirement):** a second checkout with a different `COMPOSE_PROJECT_NAME` + `HTTP_PORT` → two independent stacks coexist, no container/port/volume collision (`docker compose ls`), with no DB port published by either.
7. **External DB toggle (goal 3):** drop `local-db` from `COMPOSE_PROFILES` and set `EYENED_DATABASE_HOST` → `docker compose config`/`up` does **not** error on a dangling `depends_on: database`, and the stack connects to the external DB.
8. **Attached to the shared dev database:** with the real `storage-mounts.json` and `PLATFORM_STORAGE_PATH`, existing images and thumbnails render — proving the generated config reproduces today's hand-maintained setup.
9. **Prod + client layering (goal 3):** `make prod` (plus a throwaway `compose.<client>.yaml` + `.env.<client>`) brings up the production build (gunicorn, built client on 4173 upstream).
10. **Snapshot/restore:** `make db-snapshot` then `make db-restore` returns `alembic current` to the pre-migration revision.
11. **Optional OIDC:** add `oidc` to `COMPOSE_PROFILES` → Keycloak starts and the OIDC login flow works.
12. **Regression:** the existing `pytest` suite still passes. Run `graphify update .` after the change per project convention.
