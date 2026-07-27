# Design: Consolidate app bootstrapping into one `deploy/` directory

Date: 2026-07-24 (extended 2026-07-27; client-onboarding amendment 2026-07-27)
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
3. **A client clones the public repo and gets a working local install.** This is goal 2's concrete form and the one that constrains the design hardest: the repo is public, `docs/` publishes to GitHub Pages from `main`, and `docs/…/getting_started.mdx` is the page an external adopter actually follows. The install they get must be a *production* one — not the developer stack — and the published instructions must describe this repo, not the one it replaces.
4. **Handle multi-site deployments and debugging later** — one shared base with prod/per-site layers; external/managed DB one setting away; multiple isolated stacks on one host.

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

### Two prompts block unattended database setup

They behave differently, and only one of them needs changing.

`orm/migrations/alembic/env.py:56-65` calls bare `input()` for any command outside `{revision, history, current, heads, branches, show, check, list_templates, stamp}` — `upgrade` prompts. There is no `-x` flag, env var, or TTY check, so a non-interactive `upgrade` dies. The design **routes around this rather than changing it**: bootstrap uses the fresh-install path and only ever calls `current` and `heads`, which are already exempt.

`orm/eyened_orm/commands/shared.py:24-31` is the harder one. `get_database(confirmation=True)` — used by `initialize-database` (`cli.py:86`) and `load-dump` (`cli.py:467`) — prints a **randomly generated four-letter code** and requires it typed back, so it cannot be piped past at all. There is no `--yes` flag. This is the single thing standing between the current code and a one-command bootstrap.

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
10. **Bootstrap is gated on database state, not on which stack is running.** It runs whenever this stack **owns** its database (`local-db` profile on) *and* that database is **empty** — creating the schema, seeding form schemas, and creating an admin. It **never migrates an existing database**; drift is reported, not fixed. Deliberately not "runs on the dev path": tying it to dev would leave the client install — the one that most needs it — with no bootstrap at all.
11. **Migrations are container-only.** `dev/.env.alembic` disappears; host access to MySQL is opt-in, not default.
12. **Environment-neutral names.** `DEV_NGINX_PORT` → `HTTP_PORT` and `DEV_PUBLIC_HOST` → `PUBLIC_HOST`: both serve prod as well as dev in the unified stack, so the `DEV_` prefix is actively misleading. The only consumers are the Keycloak service and `keycloak/entrypoint.sh`, which this change is already moving and rewriting.
13. **The client install is `./install.sh`** — the production build on a bundled database, bootstrapped. It is a script, not a `make` target, because **Docker must be the only prerequisite**: `make` is absent on Windows, arrives on macOS only with the Xcode Command Line Tools, and is a package install on minimal Linux images. Asking a non-technical adopter to install a build tool before step one contradicts goal 3. `make install` exists as a one-line alias for developers who already think in targets; `make up` remains the developer stack.
14. **The published docs are in scope.** `docs/src/content/docs/` is the client's entry point and is deployed from `main`; the four pages that describe the stacks being deleted are part of this change, not follow-up work.
15. **Supported platforms are stated: Linux and macOS natively, Windows via WSL2.** Scripts stay POSIX `sh` and degrade when optional host tools are missing.
16. **Clients install from a release tag, not from a branch.** A preflight (`doctor.sh`) runs before anything is built.
17. **Day-2 operations need no `make` either.** Because the install writes `COMPOSE_FILE` into `deploy/.env`, a bare `docker-compose logs -f` / `down` / `up -d` run from `deploy/` resolves the right layers with no `-f` juggling. The published docs use that plain form; `make logs` / `make down` are developer shorthand for the same thing.

## Design

### Target layout

```
deploy/
  compose.yaml                # base: all services; local-db + oidc profiles; prod-ready defaults
  compose.override.yaml       # dev layer (named in COMPOSE_FILE — see below)
  compose.local-db.yaml       # bundled-DB layer: server depends_on database (see below)
  compose.prod.yaml           # prod/deploy layer (client install + sites; excludes dev override)
  compose.storage.yaml        # GENERATED from storage-mounts.json (gitignored)
  Dockerfile.server           # unified (one build; run command set per env in compose)
  Dockerfile.client           # multi-stage: shared base -> `dev` and `prod` targets
  nginx/
    default.conf.template     # base proxy + thumbnails; client port via ${CLIENT_UPSTREAM_PORT}
    storage.d/storage.conf    # GENERATED per-backend `location` blocks (gitignored)
  entrypoint-client.sh        # moved from dev/
  keycloak/                   # moved from dev/keycloak/ (realm template + entrypoint)
  scripts/
    gen-storage.sh            # storage-mounts.json -> compose overlay + nginx conf + env var
    bootstrap.sh              # first-run: create schema + seed + admin user (idempotent)
    doctor.sh                 # preflight: compose version, port, daemon, disk
    load_dump.sh              # moved from database/, compose paths updated
    save_dump.sh              # moved from database/
  storage-mounts.json.example # committed template
  .env.example                # single committed template (working local defaults)
  README.md                   # the one bootstrap doc
install.sh                    # (root) THE client entry point — POSIX sh, Docker its only dependency
Makefile                      # (root) install/doctor/up/down/logs/prod/reset/migrate/db-shell/
                              #        db-snapshot/db-restore/check-storage + first-run .env creation
.dockerignore                 # (root) trim the `context: ..` build context
```

Per-site deploys add `deploy/compose.<site>.yaml` + `deploy/.env.<site>` (gitignored), layered on `compose.prod.yaml`. **`<site>`, not `<client>`** — `client` already names the frontend service in this compose file, and the word now also means the organization running the deployment; one of the two had to give.

### Compose layering — one base serves the developer stack, the client install, and per-site deploys

- **`compose.yaml` (base)** — the shared service graph and prod-ready defaults: `database` + `adminer` under a `local-db` profile; `redis`; `server` (build `Dockerfile.server`, default = prod `gunicorn` CMD, healthcheck); `client` (build target `prod`); `fileserver` (nginx; mounts `./nginx/default.conf.template` into `/etc/nginx/templates/` **and** `./nginx/storage.d` into `/etc/nginx/storage.d` — the latter always, since an empty directory is valid; default `CLIENT_UPSTREAM_PORT=4173`). `keycloak` under an `oidc` profile. Named volumes `db_data`, `platform_storage`, `client_node_modules`. **No hardcoded `name:`** — the project name comes from `COMPOSE_PROJECT_NAME`. **Pin all images** (`nginx:1.27-alpine`, `adminer:4.8.1`, `redis:7-alpine`, `mysql:8.0.27`) — no `latest`; today's dev stack runs `nginx:latest` and `adminer:latest`. The `database` service carries a **healthcheck** (`mysqladmin ping`, ~5s interval / 10 retries) — note this is a liveness signal only: `ping` reports success even when credentials are rejected, and a password passed inline would be visible in `ps`, so pass it via `--defaults-extra-file` or omit it.
- **`compose.override.yaml` (dev)** — dev refinements only: `client` build target `dev` with `CLIENT_UPSTREAM_PORT=5173`; `server` `command:` → `uvicorn --reload` plus source bind mounts (`../server`, `../orm`); `client` node_modules volume + `../client` bind mount; modest **resource limits** on `database`/`server` — important because many devs share one host. Use `deploy.resources.limits` throughout (Compose v2 honors it outside swarm) rather than mixing it with the older `mem_limit` style. `deploy/.env.example` ships `COMPOSE_PROFILES=local-db`.
- **`compose.local-db.yaml` (bundled DB)** — one thing: **`server depends_on database: condition: service_healthy`** (see below). It is a layer of its own rather than part of the dev override because the client install runs the bundled database *without* the dev layer; parking the dependency in the dev override would leave `./install.sh` racing MySQL on first boot, which is exactly the crash-loop this dependency exists to prevent.
- **`compose.prod.yaml` (prod/deploy)** — prod-only concerns not already in the base: `restart:` policies and `deploy.resources` limits. It makes **no assumption about where the database lives**. That choice is already expressed by the `local-db` profile plus `EYENED_DATABASE_HOST`, and keeping it out of this layer is what lets one prod layer serve both a client's self-contained install and a site pointed at a managed database.
- **`compose.storage.yaml` (generated)** — dataset bind mounts only.

**How the layers are selected (verified, and not the obvious answer).** Compose's automatic `compose.override.yaml` discovery is **disabled the moment `COMPOSE_FILE` is set**. Tested: with three files present and no `COMPOSE_FILE`, `config --services` yields `base overridden`; with `COMPOSE_FILE=compose.yaml:compose.storage.yaml` it yields `base storage` — the dev layer silently disappears. Since the generated storage layer has to come in through `COMPOSE_FILE`, that variable must name **every** layer:

```bash
# deploy/.env — every layer is explicit; there is no implicit override pickup.
# Developer stack (written by `make up`):
COMPOSE_FILE=compose.yaml:compose.override.yaml:compose.local-db.yaml:compose.storage.yaml
# Client install (written by `./install.sh`) — same minus the dev override, plus prod:
# COMPOSE_FILE=compose.yaml:compose.local-db.yaml:compose.storage.yaml:compose.prod.yaml
COMPOSE_PROFILES=local-db
```

An explicit `-f` list on the command line overrides `COMPOSE_FILE` entirely, which is how `make prod` drops the dev layer and why it must re-list the storage layer itself.

**Startup ordering & the external-DB toggle (correctness):** the `server → database` `depends_on` must live **only** in `compose.local-db.yaml`, **never in the base**. If an always-on `server` in the base declared `depends_on: database` while `database` is gated behind `profiles: [local-db]`, then turning the profile off (external DB) would make Compose refuse to start — it cannot depend on a disabled service. Keeping the dependency in its own layer means: bundled DB → server waits for MySQL to report healthy (no first-run crash-loop); external DB → no `database` service, no dangling dependency.

The cost is that "use the bundled database" is expressed **twice** — `local-db` in `COMPOSE_PROFILES` *and* `compose.local-db.yaml` in `COMPOSE_FILE` — because a compose file layer is merged unconditionally and cannot itself be profile-gated. Setting one without the other fails in an unhelpful way: profile-without-layer silently drops the health dependency, layer-without-profile is the dangling-`depends_on` error above. `make doctor` therefore checks the two agree and says which one to change, turning a footgun into a checked invariant.

Behavior — three entry points, one base:

| Target | Layers | Database | Server | Bootstrap |
|---|---|---|---|---|
| `./install.sh` (client) | base + local-db + prod + storage | bundled | gunicorn, built client | yes (empty DB) |
| `make up` (developer) | base + override + local-db + storage | bundled | `uvicorn --reload`, source mounted | yes (empty DB) |
| `make prod` (site/deploy) | base + prod + storage [+ site] | external | gunicorn, built client | no (declines to touch it) |

None of the three is a bare `docker-compose up` typed from memory, precisely because the file list is no longer implicit — each entry point owns its layer list, and records it in `.env` so later commands inherit it.

### Compose invocation (host reality, verified)

The shared dev host has **no `docker compose` plugin** — `docker: 'compose' is not a docker command` — only the standalone binary, `docker-compose` v2.15.1, against Docker Engine 26.1.3. Every `docker compose …` line in the current READMEs therefore fails there as written.

Both entry points resolve the binary once (`docker compose` if the plugin answers, else `docker-compose`) and route every invocation through it — the `Makefile` via a variable, `install.sh` via a shell function. `install.sh` must also **print the day-2 commands using the binary it resolved**, since telling a client to run `docker compose logs` on a host that only has `docker-compose` recreates the exact failure this section exists to prevent. `deploy/README.md` shows both forms. Because the floor is 2.15, the design must not use the top-level `include:` key (Compose 2.20+); layering stays on `COMPOSE_FILE` and `-f`, both of which work at 2.15. `--wait`, profiles, `depends_on: condition: service_healthy`, and `deploy.resources.limits` outside swarm are all available at that version.

### Storage configuration — one file, three derived artifacts

`deploy/storage-mounts.json` (untracked, `.example` committed) is the single source of truth:

```json
{
  "oogergo": "/mnt/oogergo",
  "genr": "/mnt/genr"
}
```

`deploy/scripts/gen-storage.sh`, run by `./install.sh` and `make up` alike, emits:

1. `EYENED_STORAGE_MOUNTS` (compact JSON) into the `server` and worker environments — Python reads files locally, no API round-trip.
2. `deploy/compose.storage.yaml` — one `- <path>:<path>:ro` bind mount per key, on `fileserver` and `server`.
3. `deploy/nginx/storage.d/storage.conf` — one `location /<key>/ { internal; alias <path>/; }` per key.

**The snippet must not go in `conf.d/`.** The stock nginx image includes `/etc/nginx/conf.d/*.conf` inside the `http{}` block (`nginx.conf:31`), and `20-envsubst-on-templates.sh` renders templates into that same directory — so a bare `location` block there is a startup failure, verified: `nginx: [emerg] "location" directive is not allowed here`. Instead the snippet mounts at `/etc/nginx/storage.d/` and `default.conf.template` carries `include /etc/nginx/storage.d/*.conf;` **inside its `server{}` block**. A glob that matches nothing is valid nginx, so a clean clone with no mounts still passes `nginx -t` — both cases were tested against `nginx:1.27-alpine`.

Both generated files are gitignored, and the generator always writes them (empty when there are no mounts) because `COMPOSE_FILE` names `compose.storage.yaml` — a missing file would break `docker compose` before `make` ever ran. An empty `storage-mounts.json` is exactly right for a clean clone: a fresh bundled database has **no `StorageBackend` rows** (`eorm initialize-database` creates none), so a newcomer configures no mounts at all. Mount configuration is a property of the database you attach to, which is why it must not live in a committed shared file.

Because keys must match `StorageBackend.Key`, a separate `make check-storage` target reports configured keys with no matching row and rows with no configured mount. It is deliberately *not* part of `./install.sh` or `make up`: generation must work before any database exists, which is exactly the state a client's first run is in.

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

One committed template with **working local defaults** (dev-only passwords, clearly marked not-for-prod) so `./install.sh` and `make up` from a clean clone both work with zero editing on a solo machine. Names are consolidated onto the canonical `EYENED_*` set (per `docs/src/content/docs/orm/configuration.mdx`). Sections:

- **Per-developer isolation (shared host):** `COMPOSE_PROJECT_NAME=eyened` (comment: set to `eyened-<yourname>` on the shared server) and `HTTP_PORT` / `ADMINER_PORT` (comment: pick unique per dev). Renamed from `DEV_NGINX_PORT` because the same variable serves prod; `DEV_PUBLIC_HOST` becomes `PUBLIC_HOST` for the same reason. Both are consumed by the Keycloak compose service and `keycloak/entrypoint.sh` (OIDC redirect + web origin), which move under `deploy/` and get updated with them.
- **Database:** bundled defaults; `DB_PUBLISH_PORT` present but **commented out** — the server reaches MySQL in-network at `database:3306`, so no host port is published by default (the biggest source of cross-dev collisions). A dev who wants DBeaver or a host-side alembic uncomments it and picks a unique value. A commented block shows how to point at an external DB instead.
- **Storage:** `PLATFORM_STORAGE_PATH` (commented out; defaults to the named volume). `EYENED_STORAGE_MOUNTS` is *not* hand-written here — it is generated from `storage-mounts.json`.
- **API:** `EYENED_API_SECRET_KEY`, plus correctly-named `EYENED_API_URL` / `EYENED_API_USERNAME` / `EYENED_API_PASSWORD` (only needed by hosts without mounts — notebooks, remote workers), with a comment saying so.
- **Layer selection:** `COMPOSE_FILE` (dev list active, client list commented beside it — see the layering section) and `COMPOSE_PROFILES=local-db` (add `oidc` to enable Keycloak). These two must agree; `make doctor` checks that they do.
- **Secrets:** real values only ever in the untracked `.env` / `.env.<site>`.

### Root entry points: `install.sh` (clients) and `Makefile` (developers)

Two doors into the same machinery. The script is the published one because it has no prerequisite beyond Docker; the Makefile is developer ergonomics.

- **`./install.sh` — the client entry point.** POSIX `sh`. Runs `deploy/scripts/doctor.sh`; creates `deploy/.env` and `storage-mounts.json` from their examples if missing, generating a fresh `EYENED_API_SECRET_KEY`; runs `gen-storage.sh`; brings the stack up `-d --build`; runs `bootstrap.sh`; prints the URL, the one-time admin password, and the day-2 commands. What a client gets is the **production** stack — gunicorn, built client, no source bind mounts — on a database this stack owns. It is idempotent: re-running it on an installed stack rebuilds and re-bootstraps harmlessly.

  **The install records which stack this is**, by writing a `COMPOSE_FILE` naming the client layers (`compose.yaml:compose.local-db.yaml:compose.storage.yaml:compose.prod.yaml`) into `deploy/.env`; `make up` writes the dev list instead, and `.env.example` ships the dev list with the client one commented beside it. This one line is what makes everything afterwards work without `make` **or** `-f` flags: a bare `docker-compose logs -f`, `docker-compose down`, or `docker-compose up -d` run from `deploy/` resolves exactly the layers that are running. Had the install written nothing, those same commands would silently resolve against the developer layer and report on a `server` that isn't the one up. So the day-2 instructions in the published docs are plain `docker-compose`, and a client never needs a build tool at all.
- **`make install`** — a one-line alias for `./install.sh`, so developers who live in the Makefile do not have to remember which door is which. It adds nothing; the script is the implementation.
- `make doctor` (= `deploy/scripts/doctor.sh`) — preflight, and the first thing `./install.sh` and `make up` do. Checks: Docker daemon reachable; compose **≥ 2.15** (the floor this design depends on, asserted everywhere and until now checked nowhere); `HTTP_PORT` not already bound (the classic first failure on a shared or busy machine); enough free disk for images plus the database volume; that `local-db` in `COMPOSE_PROFILES` agrees with `compose.local-db.yaml` in `COMPOSE_FILE`; and that the `COMPOSE_FILE` already recorded in `.env` matches the entry point being invoked — running `./install.sh` in a directory whose `.env` was written by `make up` (or the reverse) stops with an explanation rather than quietly building the other stack. Each failure names the fix, not just the symptom.
- `make up` — the developer stack. Same first-run creation as `install.sh` (`.env`, `storage-mounts.json`, generated secret key), plus the "personalize `COMPOSE_PROJECT_NAME` + `HTTP_PORT` on a shared host" note; runs `gen-storage.sh`; brings the dev stack up `-d --build`; then runs `bootstrap.sh` and prints the login URL. The shared first-run logic lives in one place so the two entry points cannot drift.

  On the generated key: **never copy the literal from the template** — that would give every deployment the same JWT signing key. Generation prefers `openssl rand -hex 32` and falls back to `python3 -c 'import secrets;print(secrets.token_hex(32))'`; neither tool is guaranteed on a stock macOS or WSL host, and both failing must be a hard error, since a silent empty signing key is far worse than a refusal to start.
- `make down`, `make logs`, `make migrate` (alembic inside the server container), `make db-shell`.
- `make prod` — `-f compose.yaml -f compose.storage.yaml -f compose.prod.yaml`. The generated storage layer **must** be listed explicitly: an explicit `-f` list overrides `COMPOSE_FILE` from `.env` (verified — with `COMPOSE_FILE=compose.yaml:compose.storage.yaml`, adding `-f compose.yaml -f compose.prod.yaml` yields `base prod` and silently drops `storage`), and prod serves images through the same mounts dev does. It differs from `./install.sh` in exactly one layer: no `compose.local-db.yaml`, because the database is someone else's.
- `make reset` (down + volumes) — requires a typed confirmation, and refuses outright when `PLATFORM_STORAGE_PATH` or an external `EYENED_DATABASE_HOST` is set, so it cannot be aimed at shared or production data.
- `make db-snapshot NAME=…` / `make db-restore NAME=…` — cold tar of the MySQL data volume, container and volume names derived from `COMPOSE_PROJECT_NAME`. This generalizes the currently hand-written procedure in `plan.md`, whose commands hardcode one developer's container name. The safety net matters because MySQL auto-commits DDL per statement, so a half-applied migration cannot be reliably undone with `alembic downgrade`.
- Keep the existing `gen-openapi` / `gen-types` targets.

`deploy/README.md` documents both halves of rollback: **data** via `make db-restore`, and **application** via checking out the previous release tag (or reverting the commit, for developers) and re-running `./install.sh` / `make up`. Images are built from source, so **the checkout is the artifact** until registry-based images land — which is the reason clients are told to install from a tag rather than a branch.

### First-run bootstrap (`deploy/scripts/bootstrap.sh`)

Runs from **`./install.sh` and `make up` alike** — the two entry points where this stack owns its database — and never from `make prod`. It is idempotent:

1. Wait for the `database` service to report healthy. With the `local-db` profile off there is no such service, so bootstrap reports that it cannot verify an external database and exits without touching it. This, not the choice of compose layers, is what keeps bootstrap away from a database it does not own.
2. **Empty database** → `eorm initialize-database --seed-form-schemas`. This is the supported fresh-install path: it runs `Base.metadata.create_all` and **stamps** Alembic at head (`cli.py:95-107`), so later upgrades apply only new migrations (`docs/…/release_notes.mdx:19`). Do **not** use `alembic upgrade head` here — replaying the whole migration chain from zero is not a path this repo maintains.
3. **Existing database** → compare `alembic current` against `heads`. Equal: say so and do nothing. Behind: print both revisions and tell the operator to run `make migrate`. Never migrate an existing database implicitly — the same `.env` can point at shared or production data.
4. If no accounts exist → `eorm create-user` for username `admin` with a password **generated at first run and printed once**, the same treatment as `EYENED_API_SECRET_KEY` (passing `--password` on the command line suppresses click's prompt). Otherwise skip. These are deliberately **not** `EYENED_API_USERNAME` / `EYENED_API_PASSWORD`: those name an account the ORM uses to call the API from a host without mounts, which is a different thing from the human admin created here, and conflating them would make one variable mean two things.

**The one interactive gate in the way, and how it is resolved**

`eorm initialize-database` goes through `get_database(confirmation=True)` (`orm/eyened_orm/commands/shared.py:24-31`), which prints a **randomly generated four-letter code** and requires it typed back. Unlike a `[y/N]` prompt this cannot be piped past — the code is created at runtime — so the command is unautomatable as written.

The fix is not a skip flag and not a declared-target env var. Both were considered and rejected: a flag (`EYENED_ASSUME_YES`) can be left switched on in `.env` and silently disarms every later command in that container; a declared target (`db@host:port`) only looks specific, because `eyened_database@database:3306` is byte-identical in every developer's stack *and* in any deployment running the bundled `local-db` profile — and its ambiguity (`database` / `127.0.0.1` / `host.docker.internal` / bare IP, port present or omitted) trains operators to edit the guard until it matches.

Instead, **make the gate reflect the actual risk, which is a property of the database's state rather than of the command**:

> `get_database(confirmation=True)` prompts only when the target database **contains tables**. On a database with no tables it proceeds, printing why.

This is sound because nothing in these commands can destroy an empty database. `Base.metadata.create_all` is create-if-not-exists. `--recreate` drops a database that holds nothing. `load-dump` loading into an empty database removes nothing. The genuine hazard is `stamp_alembic_head` (`utils/alembic_utils.py:38-44`), which on a database already at revision X jumps `alembic_version` to head so a later `upgrade head` applies **nothing** — silent schema drift — and that requires an already-versioned, non-empty database, which this rule still gates.

The rule is strictly tighter than today's prompt: it also protects the case where a human confidently types the code against a populated database. It adds **no environment variable and no configuration** — there is nothing to copy wrong between hosts. If the table check cannot be performed (connection or permission failure), it fails safe and prompts. The decision is logged loudly (`target database has no tables — proceeding without confirmation`) so it appears in `./install.sh` / `make up` output and in CI logs.

Scope: one file, `orm/eyened_orm/commands/shared.py`. Both callers (`initialize-database` at `cli.py:86`, `load-dump` at `cli.py:467`) inherit the behavior unchanged in the dangerous direction. **`orm/migrations/alembic/env.py` is deliberately untouched** — `bootstrap.sh` runs only `alembic current` and `heads`, both already in its `no_prompt_cmds` set (`env.py:45-55`), so its prompt is never reached and continues to guard manual `make migrate` runs.

### Client install from a GitHub checkout (goal 3)

The whole published path reduces to three lines, none of them an edit, and none of them requiring a tool the client does not already have:

```bash
git clone --branch v2026.07.0 https://github.com/Eyened/eyened-platform.git
cd eyened-platform
./install.sh          # preflight, build, bootstrap; prints the URL + admin password
```

That replaces an eight-step page involving two compose stacks, a hand-edited `nginx.conf`, and an interactive `eorm initialize-database`.

Day 2 is plain Compose, run from `deploy/` — no `make`, no `-f`, because the install wrote `COMPOSE_FILE`:

```bash
docker-compose logs -f      # or `docker compose` where the plugin exists
docker-compose down
docker-compose up -d
```

`install.sh` prints these three lines on success, so the operator never has to derive them.

**Clone a release tag, not a branch.** Tags already exist (`v2026.07.0`, `v0.0.4`, …) and the default branch is `main`, but nothing today tells an adopter which to take. A tag matters here more than usual because images are built from source: the checkout *is* the artifact, and the rollback story above — check out the previous tag, re-run — presumes a known-good ref to go back *to*. When registry-based images land (see deferred hardening), the image tag replaces the git tag as the unit of version, and this instruction changes with it.

**Supported platforms: Linux and macOS natively, Windows via WSL2.** **Docker is the only prerequisite** — a POSIX shell comes with all three, and `make` is deliberately not on the list: it does not exist on Windows, arrives on macOS only with the Xcode Command Line Tools, and is a separate package on minimal Linux images. Two design choices already made are what let this hold on Docker Desktop without a special case, and they are worth stating as such: `EYENED_STORAGE_ROOT` defaults to a **named volume** rather than a host bind mount (nothing to translate across the VM boundary, no permission surprises), and the bundled database publishes **no host port** by default. `install.sh`, `bootstrap.sh`, `gen-storage.sh`, and `doctor.sh` stay POSIX `sh` and fall back when an optional host tool is missing.

**Adding the first dataset.** A fresh install has an empty database, therefore **zero `StorageBackend` rows** and no images — a correct but blank viewer. Getting from there to a visible image is the step the current docs bury across three pages, and it is short:

1. Add `"<key>": "/path/to/images"` to `deploy/storage-mounts.json`.
2. Re-run whichever entry point this stack was installed with — `./install.sh` for a client, `make up` for a developer — to regenerate the compose overlay, the nginx locations, and `EYENED_STORAGE_MOUNTS`.
3. Import with `storage_backend_key: "<key>"`. The `StorageBackend` row is **created automatically** when it does not exist (`docs/…/import_metadata_fields.mdx:156`), so there is no separate "register the backend" step.
4. `make check-storage` afterwards to confirm keys and rows agree.

This is documented in `deploy/README.md` and in the published Getting Started; it is the answer to "the install worked, now what?"

### Migrations & DB init (reuse existing tooling)

Drop `dev/.env.alembic`. Migrations and init run **inside the server container**, which already has the unified env loaded and ships `/app/orm/migrations/` plus the `eorm` CLI via `pip install -e /app/orm`:

- `make migrate` → `$(COMPOSE) exec -it server alembic -c orm/migrations/alembic.ini upgrade head` (interactive, so the confirmation prompt still guards manual runs). `$(COMPOSE)` is the resolved binary from the section above — never a hardcoded `docker compose`.
- `$(COMPOSE) exec server eorm initialize-database` / `eorm seed-form-schemas` / `eorm create-user`.
- Data dumps via `deploy/scripts/{load,save}_dump.sh` and/or `eorm load-dump` / `save-dump`.

Host-side alembic remains possible for anyone who uncomments `DB_PUBLISH_PORT`, but it is no longer the documented path.

### Keycloak (optional `oidc` profile)

Fold `dev/keycloak/docker-compose.keycloak.yml` into `compose.yaml` as a service gated by `profiles: [oidc]`; keep `realm-eyened-dev.json.template` + `entrypoint.sh` under `deploy/keycloak/`, updated for `PUBLIC_HOST` / `HTTP_PORT`. Off by default so "clone and run" stays lean.

### Workers (env-aligned only)

Leave `worker/` as its own deployment. Reconcile `worker/.env.example` with the canonical set and **add `EYENED_STORAGE_MOUNTS`**, which inference and thumbnail generation need (`docs/src/content/docs/thumbnails.mdx:158`) and which the template currently omits.

## Landing plan

The prototype comes before the cutover decision. `dev/`, `docker/`, and `database/` are almost entirely bart's work, and four contributors are active with branches in flight, so the disruption is worth measuring rather than guessing.

1. Build `deploy/` on `feature/deploy-consolidation` (worktree `../eyened-platform-worktrees/deploy-consolidation`, branched from `origin/development`).
2. Verify it three ways: a clean clone via `./install.sh` (the client), a clean clone via `make up` (the developer), and this shared host attached to the existing dev database and datasets (the migration case).
3. **Then** choose how to land it — additive with `dev/`/`docker/`/`database/` marked deprecated and deleted in a follow-up PR, or a single PR that adds and deletes with an `adopt-env` helper — with evidence about what actually breaks.

**The docs constrain the cutover.** `.github/workflows/deploy.yml` publishes `docs/` to GitHub Pages **on push to `main`**, while this work lands on `development`. So the published Getting Started and the directories it names are coupled: the moment `docker/` and `database/` are deleted on `main`, the live page instructing readers to `cd eyened-platform/docker` is wrong for everyone who arrives after. The doc rewrites therefore travel in the **same** merge to `main` as the deletion — never in a follow-up — and the additive-with-deprecation option, if chosen, buys nothing here, because a public page cannot be "deprecated" for the reader who is following it right now.

Related in-flight work to reconcile before merging: open issue #151 and bart's unmerged `origin/docs/clarify-storage-mounts-151`, whose two-layer framing this design adopts.

## File-level impact

**Create:** `deploy/compose.yaml`, `deploy/compose.override.yaml`, `deploy/compose.local-db.yaml`, `deploy/compose.prod.yaml`, `deploy/Dockerfile.server`, `deploy/Dockerfile.client`, `deploy/nginx/default.conf.template`, `deploy/scripts/gen-storage.sh`, `deploy/scripts/bootstrap.sh`, `deploy/scripts/doctor.sh`, `deploy/storage-mounts.json.example`, `deploy/.env.example`, `deploy/README.md`, **root `install.sh`** (the published client entry point), root `Makefile` targets, root `.dockerignore`.

**Move (with path fixes):** `dev/entrypoint-client.sh`, `dev/keycloak/*`, `database/load_dump.sh`, `database/save_dump.sh` → under `deploy/`. The Keycloak service definition and `keycloak/entrypoint.sh` carry the only `${DEV_PUBLIC_HOST}` / `${DEV_NGINX_PORT}` references in the repo (OIDC redirect URI, web origin, issuer validation) and are rewritten to `PUBLIC_HOST` / `HTTP_PORT` as they move.

**Modify (code):** `orm/eyened_orm/commands/shared.py` only — `get_database(confirmation=True)` prompts when the target database has tables and proceeds (loudly) when it has none. No new env var, no flag, and `orm/migrations/alembic/env.py` stays as it is.

**Delete (superseded, timing per the landing plan):** `dev/docker-compose.yml`, `dev/Dockerfile.server`, `dev/Dockerfile.client`, `dev/nginx.conf`, `dev/.env`, `dev/.env.alembic`, `dev/sample.env`, `docker/*`, `database/docker-compose.yaml`, `database/.env`, `database/.env.example`. Merge useful prose from `dev/README.md`, `docker/README.md`, `database/README.md` into `deploy/README.md`. (`dev/generate_openapi.py` is dev tooling, not env/docker — leave it.)

**Update:** root `.gitignore` (remove `dev/docker-compose.yml`, `docker/.env`; add `deploy/.env`, `deploy/.env.*` with `!deploy/.env.example`, `deploy/storage-mounts.json`, `deploy/compose.storage.yaml`, `deploy/nginx/storage.d/storage.conf`); root `README.md` "Repository overview"; `worker/.env.example`.

**Update (published docs — the client's entry point, and not optional):** these four pages describe the stacks this design deletes, and `docs/` is deployed to GitHub Pages by `.github/workflows/deploy.yml`.

| Page | Old-stack references | Change |
|---|---|---|
| `docs/src/content/docs/getting_started.mdx` | 12 | Replace the 8-step Quick Setup (`cd docker`, `cd ../database`, hand-edit `nginx.conf`, interactive `eorm initialize-database`) with clone-a-tag → `./install.sh` → open the URL, plus the "add your first dataset" flow and plain `docker-compose` day-2 commands. |
| `docs/src/content/docs/guides/development_setup.mdx` | 19 | Becomes the developer page: `make up`, hot reload, `make migrate`, `COMPOSE_PROJECT_NAME` / `HTTP_PORT` on a shared host. Drops the `database/` + `dev/` two-stack dance and the `DEV_NGINX_PORT` name (Decision 12). |
| `docs/src/content/docs/platform_design.mdx` | 4 | The storage section still instructs "configure a matching nginx `location` and read-only mount for each backend" — superseded by `storage-mounts.json` and the generator. |
| `docs/src/content/docs/release_notes.mdx` | 1 | Record the consolidation and the `DEV_*` → `HTTP_PORT` / `PUBLIC_HOST` rename, since both break existing `.env` files. |

**Reuse (do not reinvent):** nginx `*.template` env substitution; the `server` healthcheck + `adminer`/`xtrabackup` profile patterns; `eorm initialize-database` / `seed-form-schemas` / `create-user` / `load-dump` / `save-dump`; the `EYENED_*` schema in `docs/src/content/docs/orm/configuration.mdx`.

## Out of scope

- Pulling `worker/` GPU stacks into the unified compose (they deploy to separate GPU hosts).
- Application/business-logic code changes. (Making the confirmation gate in `commands/shared.py` state-based is CLI tooling and is the sole exception.)
- Fixing the underlying zarr concurrency issues, issue #119 (tracked separately). This design reduces exposure by defaulting new stacks away from the production store, but does not fix the store.
- **Shipping a demo dataset.** A client's install lands on an empty, working platform, and the documented first step is importing their own images. Bundling sample ophthalmic images raises licensing and patient-data questions that this change should not decide, and the repo ships none today. The cost is that "it works" and "I can see something" remain two steps rather than one — worth revisiting if adopter feedback says the blank viewer reads as a failed install.

## Future / deferred hardening

- **Registry-based images + image scanning.** Prod, `./install.sh`, and multi-site all build images on each host (non-reproducible, unscanned, and slow on a client's first run — the largest remaining cost in "clone and go"). Forward path: CI builds, `trivy`-scans, and pushes tagged images to GHCR, with `compose.prod.yaml` referencing the pinned tag instead of `build:`. That also replaces "clone a release tag" with "pull an image tag" as the client's unit of version.
- **Secrets management for prod.** Per-site secrets in `.env.<site>` should graduate to Compose `secrets:` or an external manager.
- **Non-root prod containers** — cheap to add to the Dockerfile prod stages when the prod layer is first exercised.
- **Deriving mounts from the database.** Issue #151 asks why operators maintain a key→path map at all. `StorageBackend.Config` (a JSON column, currently an unused placeholder) could carry a default path, letting the generator read the DB. Deferred: it inverts the bootstrap order (nginx config would depend on a running database) and physical paths differ per deployment, which is exactly what env config is for.

## Verification

1. **Clean-clone client install (goal 3):** from a fresh `git clone --branch <tag>` in a directory with no prior state, `./install.sh` alone → MySQL healthy, schema created and stamped at head, form schemas seeded, admin created with a printed one-time password, UI at `http://<host>:${HTTP_PORT}`, `/api/health` responding. No file edited by hand. Then prove it is genuinely the production stack, not the dev one wearing a different name: the `server` process is **gunicorn** (not `uvicorn --reload`), `docker inspect` shows **no bind mount** of `../server` or `../client`, and editing a source file changes nothing until a rebuild.
2. **Docker really is the only prerequisite:** run the whole of item 1 **with `make` removed from `PATH`**, then run the printed day-2 commands (`docker-compose logs -f`, `down`, `up -d`) from `deploy/` the same way — all succeed, and `logs` shows the gunicorn server rather than a dev container. This is the regression test for the entry point being a script: nothing on the client path may reach for a build tool, and nothing may require an `-f` list the operator has to assemble.
3. **Clean-clone dev bring-up (goals 1+2):** the same from `make up` → hot-reload server, vite client, everything else as above. No manual editing on a solo machine, and no dataset mounts configured. `make install` produces byte-identical behavior to `./install.sh`, since it is an alias.
4. **`make doctor` earns its place:** with `HTTP_PORT` already bound it fails and names the port; against a compose older than 2.15 it fails and names the version; with `local-db` in `COMPOSE_PROFILES` but `compose.local-db.yaml` missing from `COMPOSE_FILE` (and the reverse) it fails and says which one to change; invoked as `./install.sh` against a `.env` that `make up` wrote, it stops instead of building the other stack. Each message states the fix. It runs before anything is built, so a failing preflight costs seconds, not a full image build.
5. **Idempotence and drift reporting:** a second `./install.sh` / `make up` on the populated stack re-runs bootstrap harmlessly — no duplicate admin, no implicit migration, no error. Against a database deliberately left one revision behind head, it prints current vs head and points at `make migrate` instead of silently continuing.
6. **Secrets are per-deployment:** two fresh `.env` files carry **different** `EYENED_API_SECRET_KEY` values, and the admin password is generated rather than shipped. Also with `openssl` removed from `PATH`: the fallback produces a real key, and with both `openssl` and `python3` absent the install **fails loudly** rather than writing an empty one.
7. **`make reset` is guarded:** it refuses while `PLATFORM_STORAGE_PATH` or an external `EYENED_DATABASE_HOST` is set, and otherwise requires the typed confirmation before removing volumes.
8. **The confirmation gate still bites where it matters:** against a **populated** database, `eorm initialize-database` run non-interactively still stops and demands the code — unattended bootstrap succeeds only on an empty database. On an empty one it proceeds and logs why. This is the regression test for the `shared.py` change; `alembic upgrade head` continues to prompt on manual runs.
9. **The in-process read bug is actually fixed:** in the server container, `image.pixel_array` on a real image returns data instead of raising `ValidationError`. This is the regression proof for the two env bugs.
10. **Generated artifacts match their source:** `compose.storage.yaml` and `nginx/storage.d/storage.conf` contain exactly the keys in `storage-mounts.json`; an image request served through nginx via X-Accel resolves from the right mount.
11. **nginx accepts both extremes:** `nginx -t` passes with an empty `storage.d/` (clean clone) and with generated locations. This is the regression test for putting the snippet outside `conf.d/`.
12. **Every layer is present in all three modes:** `config --services` for `make up` lists the dev-override services *and* the storage mounts (the check that naming `COMPOSE_FILE` did not silently drop the override); for `./install.sh`, the storage mounts and the `database` dependency but **not** the dev override; for `make prod`, the storage mounts and **neither** the dev override nor `compose.local-db.yaml`.
13. **First dataset, from zero (goal 3):** starting from the clean client install — no `StorageBackend` rows — add one key to `storage-mounts.json`, re-run, import one image with that `storage_backend_key`, and view it in the browser. The backend row is created by the import, and `make check-storage` then reports no mismatch. This is the "install worked, now what?" path end to end.
14. **Hot reload (goal 1):** edit a `server/` file and a `client/` file → server reloads and Vite HMR updates without a rebuild.
15. **Multi-dev isolation (the `-kaustav` requirement):** a second checkout with a different `COMPOSE_PROJECT_NAME` + `HTTP_PORT` → two independent stacks coexist, no container/port/volume collision (`$(COMPOSE) ls`), with no DB port published by either.
16. **External DB toggle (goal 4):** drop `local-db` from `COMPOSE_PROFILES` **and** `compose.local-db.yaml` from `COMPOSE_FILE`, set `EYENED_DATABASE_HOST` → `config`/`up` does **not** error on a dangling `depends_on: database`, the stack connects to the external DB, and bootstrap declines to touch it.
17. **Attached to the shared dev database:** with the real `storage-mounts.json` and `PLATFORM_STORAGE_PATH`, existing images and thumbnails render — proving the generated config reproduces today's hand-maintained setup.
18. **Prod + per-site layering (goal 4):** `make prod` (plus a throwaway `compose.<site>.yaml` + `.env.<site>`) brings up the production build (gunicorn, built client on 4173 upstream) against an external database.
19. **Snapshot/restore:** `make db-snapshot` then `make db-restore` returns `alembic current` to the pre-migration revision.
20. **Optional OIDC:** add `oidc` to `COMPOSE_PROFILES` → Keycloak starts and the OIDC login flow works against `PUBLIC_HOST` / `HTTP_PORT`, confirming the rename reached the realm template and entrypoint.
21. **Compose binary fallback:** every entry point works on a host with only standalone `docker-compose` (the shared dev box) as well as one with the `docker compose` plugin — including the day-2 commands `install.sh` prints, which must name the binary that host actually has.
22. **Non-Linux host:** `./install.sh` completes on macOS or WSL2. If that run cannot happen before merge, the docs claim only what was actually exercised — an untested support matrix is worse than a narrow one, because it fails in the hands of the audience least able to debug it.
23. **Published docs are consistent with the tree:** no page under `docs/src/content/docs/` — and no `README.md` — references a directory the landing plan deleted, or the names `DEV_NGINX_PORT` / `DEV_PUBLIC_HOST`. Mechanical: grep for `dev/`, `docker/`, `database/`, and `DEV_` across `docs/` and expect zero hits outside history/release notes. This is the regression test for goal 3, and the one most likely to be forgotten, because nothing in CI fails when a doc goes stale.
24. **Regression:** the existing `pytest` suite still passes. Run `graphify update .` after the change per project convention.
