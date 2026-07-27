# `deploy/` Bootstrap Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four scattered Docker stacks (`dev/`, `docker/`, `database/`, plus per-developer gitignored compose files) with one `deploy/` directory that a client can install from a GitHub checkout with `./install.sh` and a developer can run with `make up`.

**Architecture:** One `compose.yaml` base holds the whole service graph with production-ready defaults; thin layers (`compose.override.yaml` for dev, `compose.local-db.yaml` for the bundled database, `compose.prod.yaml` for deployments, `compose.storage.yaml` generated from `storage-mounts.json`) are selected by an explicit `COMPOSE_FILE` list that each entry point writes into `deploy/.env`. All logic lives in POSIX `sh` scripts under `deploy/scripts/`; `install.sh` (root) is the published client door and the `Makefile` is a thin alias layer for developers, so nothing on the client path needs a build tool.

**Tech Stack:** Docker Compose v2.15+, nginx 1.27-alpine (envsubst templates + `X-Accel-Redirect`), MySQL 8.0.27, Redis 7-alpine, Python 3.12 / FastAPI / SQLAlchemy / Alembic, Node 24 / Vite, POSIX `sh`, GNU Make (developers only), Astro Starlight docs.

**Spec:** `docs/superpowers/specs/2026-07-24-bootstrap-consolidation-design.md` (commit `4b03f88`). Where this plan resolves something the spec left at the level of intent, the task says so under **Spec note**.

**Branch:** `feature/deploy-consolidation` in the worktree `/home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation`. Never touch `feature/rbac-step2-authz` — another agent is working there.

## Global Constraints

These apply to every task; each task's requirements implicitly include this section.

- **Compose floor is 2.15.** The shared dev host has no `docker compose` plugin — only standalone `docker-compose` **v2.15.1** against Docker Engine 26.1.3. Do not use the top-level `include:` key (2.20+). `--wait`, profiles, `depends_on: condition: service_healthy`, and `deploy.resources.limits` outside swarm are all available at 2.15.
- **Never hardcode a compose binary.** Resolve it once (`docker compose` if the plugin answers, else `docker-compose`) and route every invocation through the resolved value — including any command a script *prints* for the operator to run.
- **`COMPOSE_FILE` must name every layer.** Setting it disables Compose's automatic `compose.override.yaml` discovery (verified). An explicit `-f` list on the command line overrides `COMPOSE_FILE` entirely (verified).
- **Scripts on the client path are POSIX `sh`.** `install.sh`, `deploy/scripts/lib.sh`, `doctor.sh`, `gen-storage.sh`, `bootstrap.sh`, `up.sh`, `reset.sh`, `check-storage.sh`, `compose-bin.sh`: no bashisms (`[[`, arrays, `${var,,}`, `set -o pipefail`, `/dev/tcp`). `sed -i` is not portable (GNU vs BSD) — write a temp file and `mv`. The dump scripts (`load_dump.sh`, `save_dump.sh`) stay `bash`; they are developer tools, not on the client path.
- **Docker is the only prerequisite** for the client path. `make`, `openssl`, `jq`, `nc` may all be absent; degrade or fail loudly, never silently.
- **Pin every image.** `nginx:1.27-alpine`, `adminer:4.8.1`, `redis:7-alpine`, `mysql:8.0.27`, `quay.io/keycloak/keycloak:26.0`, `percona/percona-xtrabackup:8.0`. No `latest`.
- **Environment-neutral names.** `DEV_NGINX_PORT` → `HTTP_PORT`, `DEV_PUBLIC_HOST` → `PUBLIC_HOST`, `DEV_KEYCLOAK_PORT` → `KEYCLOAK_PORT`. No `DEV_` prefix survives.
- **`<site>`, not `<client>`,** for per-deployment layers: `client` already names the frontend service.
- **Secrets only in untracked files.** `deploy/.env` and `deploy/.env.<site>` are gitignored; `.env.example` carries placeholders that first run replaces with generated values.
- **No hardcoded `name:`** in any compose file — the project name comes from `COMPOSE_PROJECT_NAME`.
- Commit after every task. Prefix commits `feat(deploy):`, `refactor(deploy):`, `docs(deploy):`, or `fix(orm):` to match the repo's convention.

**Running the Python tests** (the worktree has no venv of its own; the main checkout's venv has the interpreter and pytest, and `PYTHONPATH` makes the *worktree's* ORM win over its editable install — verified):

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
PYTHONPATH=$PWD/orm /home/kdatta/workspace/eyened-platform/dev/.venv/bin/pytest orm/eyened_orm/commands/ -q
```

## Out of scope for this plan

- **Deleting `dev/`, `docker/`, `database/`.** The spec defers the cutover shape until the prototype is verified (Landing plan). Task 16 is the decision checkpoint; the deletion itself is a follow-up.
- **Non-root prod containers.** Listed under the spec's deferred hardening. `Dockerfile.client`'s prod stage keeps the default user; revisit with registry images.
- **Registry-based images, secrets managers, deriving mounts from the database.** All deferred by the spec.
- **Pulling `worker/` into the unified stack.** Only its `.env.example` is reconciled (Task 15).

## File Structure

| File | Responsibility |
|---|---|
| `orm/eyened_orm/commands/shared.py` | Target selection + the confirmation gate, made state-based (the only application-code change) |
| `orm/eyened_orm/commands/test_shared.py` | Tests for that gate |
| `deploy/compose.yaml` | The whole service graph, prod-ready defaults, `local-db` + `oidc` + `backup` profiles |
| `deploy/compose.override.yaml` | Dev-only refinements (hot reload, source mounts, resource limits) |
| `deploy/compose.local-db.yaml` | One thing: `server depends_on database: service_healthy` |
| `deploy/compose.prod.yaml` | Restart policies + resource limits; no database assumptions |
| `deploy/compose.host-ports.yaml` | Optional: publish MySQL/Redis on the host |
| `deploy/compose.storage.yaml` | **Generated** — dataset bind mounts + `EYENED_STORAGE_MOUNTS` |
| `deploy/Dockerfile.server` | One server image; run command set per environment in compose |
| `deploy/Dockerfile.client` | Multi-stage: shared `base` → `dev` and `prod` targets |
| `deploy/nginx/default.conf.template` | Proxy + thumbnails + `include storage.d/*.conf` |
| `deploy/nginx/storage.d/storage.conf` | **Generated** — one `internal` location per storage backend |
| `deploy/scripts/lib.sh` | Shared helpers: compose resolution, secret generation, `.env` read/write, first-run setup, day-2 banner |
| `deploy/scripts/compose-bin.sh` | Prints the resolved compose binary (for the Makefile, which cannot source `lib.sh`) |
| `deploy/scripts/doctor.sh` | Preflight; every failure names the fix |
| `deploy/scripts/gen-storage.sh` | `storage-mounts.json` → compose overlay + nginx conf |
| `deploy/scripts/bootstrap.sh` | First-run schema/seed/admin, gated on database state |
| `deploy/scripts/up.sh` | Developer entry point (the dev twin of `install.sh`) |
| `deploy/scripts/reset.sh` | Guarded teardown with volumes |
| `deploy/scripts/check-storage.sh` | Compare configured keys against `StorageBackend` rows |
| `deploy/scripts/{load,save}_dump.sh` | Moved from `database/`, paths updated |
| `deploy/keycloak/` | Moved from `dev/keycloak/`, renamed vars |
| `install.sh` (root) | The published client entry point |
| `Makefile` (root) | Thin aliases over the above |

---

### Task 1: Make the `eorm` confirmation gate state-based

The single application-code change in the whole design. `get_database(confirmation=True)` prints a random four-letter code and requires it typed back, which cannot be piped — so `eorm initialize-database` is unautomatable and no unattended bootstrap is possible. Make the gate reflect the actual risk: prompt only when the target database **contains tables**.

This is sound because nothing in these commands can destroy an empty database (`create_all` is create-if-not-exists; `--recreate` drops a database holding nothing; `load-dump` into an empty database removes nothing). The genuine hazard is `stamp_alembic_head` jumping `alembic_version` to head on an already-versioned database, which this rule still gates. It adds no env var and no flag, so there is nothing to copy wrong between hosts.

**Files:**
- Modify: `orm/eyened_orm/commands/shared.py:1-33` (whole file)
- Test: `orm/eyened_orm/commands/test_shared.py` (new)

**Interfaces:**
- Consumes: `eyened_orm.Database` (has `.engine` and `.database_settings`); the `engine` fixture re-exported by `orm/eyened_orm/commands/conftest.py` (in-memory SQLite with every ORM table created).
- Produces: `get_database(*, confirmation: bool = False) -> Database` — same signature as today. Callers `initialize_database` (`orm/eyened_orm/cli.py:86`) and `load-dump` (`cli.py:467`) are unchanged. `deploy/scripts/bootstrap.sh` (Task 10) depends on this behavior: `eorm initialize-database --seed-form-schemas` must complete non-interactively against an empty database.

- [ ] **Step 1: Write the failing tests**

Create `orm/eyened_orm/commands/test_shared.py`:

```python
"""Tests for the state-based confirmation gate in get_database."""

from __future__ import annotations

import click
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from eyened_orm.commands import shared


class _FakeSettings:
    database = "eyened_database"
    host = "database"
    port = 3306


class _FakeDatabase:
    def __init__(self, engine):
        self.engine = engine
        self.database_settings = _FakeSettings()


@pytest.fixture
def empty_engine():
    """An engine whose database has no tables at all."""
    return create_engine("sqlite+pysqlite:///:memory:", future=True)


def _never_prompt(*_args, **_kwargs):
    raise AssertionError("get_database prompted when it should not have")


def test_empty_database_proceeds_without_prompting(monkeypatch, empty_engine, capsys):
    """A database with no tables is not gated, and the decision is logged loudly."""
    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(empty_engine))
    monkeypatch.setattr(shared.click, "prompt", _never_prompt)

    database = shared.get_database(confirmation=True)

    assert database.engine is empty_engine
    assert "no tables" in capsys.readouterr().out


def test_populated_database_still_demands_the_code(monkeypatch, engine):
    """A database with tables keeps the typed-code gate; a wrong code aborts."""
    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(engine))
    monkeypatch.setattr(shared.click, "prompt", lambda *a, **k: "WRONG")

    with pytest.raises(click.ClickException):
        shared.get_database(confirmation=True)


def test_populated_database_accepts_the_printed_code(monkeypatch, engine):
    """The gate still opens for an operator who types the code correctly."""
    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(engine))
    monkeypatch.setattr(shared.random, "choices", lambda *a, **k: list("ABCD"))
    monkeypatch.setattr(shared.click, "prompt", lambda *a, **k: "ABCD")

    assert shared.get_database(confirmation=True).engine is engine


def test_uninspectable_database_falls_back_to_prompting(monkeypatch, empty_engine):
    """An unreadable schema is not evidence of an empty one: fail safe, prompt."""

    def boom(_engine):
        raise SQLAlchemyError("access denied for user")

    monkeypatch.setattr(shared, "Database", lambda: _FakeDatabase(empty_engine))
    monkeypatch.setattr(shared, "inspect", boom)
    monkeypatch.setattr(shared.click, "prompt", lambda *a, **k: "NOPE")

    with pytest.raises(click.ClickException):
        shared.get_database(confirmation=True)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
PYTHONPATH=$PWD/orm /home/kdatta/workspace/eyened-platform/dev/.venv/bin/pytest \
  orm/eyened_orm/commands/test_shared.py -q
```

Expected: `test_empty_database_proceeds_without_prompting` fails with `AssertionError: get_database prompted when it should not have`, and `test_uninspectable_database_falls_back_to_prompting` fails with `AttributeError: <module 'eyened_orm.commands.shared'> has no attribute 'inspect'`.

- [ ] **Step 3: Implement the state-based gate**

Replace the whole of `orm/eyened_orm/commands/shared.py` with:

```python
from __future__ import annotations

import random
import string

import click
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from eyened_orm import Database


def _has_tables(database: Database) -> bool:
    """
    Whether the target database contains any tables.

    An unreadable schema is not evidence of an empty one, so a failed
    inspection reports True and the caller falls back to prompting.
    """
    try:
        return bool(inspect(database.engine).get_table_names())
    except SQLAlchemyError as exc:
        print(f"Could not inspect the target database ({exc}).")
        return True


def get_database(*, confirmation: bool = False) -> Database:
    database = Database()
    db_config = database.database_settings
    print(
        f"Connected to database {db_config.database} on {db_config.host}:{db_config.port}"
    )

    # The risk these commands carry is a property of the database's state, not
    # of the command: nothing here can destroy an empty database, while
    # stamp_alembic_head on a populated, already-versioned one silently skips
    # migrations. So gate on state, and say so when the gate does not apply.
    if confirmation and not _has_tables(database):
        print(
            f"Target database {db_config.database} on "
            f"{db_config.host}:{db_config.port} has no tables "
            "— proceeding without confirmation."
        )
        confirmation = False

    if confirmation:
        print("\n" + "=" * 60)
        print(
            f"Target database: {db_config.database} on {db_config.host}:{db_config.port}"
        )
        print("=" * 60)

        confirmation_code = "".join(random.choices(string.ascii_uppercase, k=4))
        print(f"\nDo you want to proceed? Type '{confirmation_code}' to confirm:")

        user_input = click.prompt("", type=str)
        if user_input != confirmation_code:
            raise click.ClickException(
                "Confirmation code does not match. Operation cancelled."
            )

    return database
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
PYTHONPATH=$PWD/orm /home/kdatta/workspace/eyened-platform/dev/.venv/bin/pytest \
  orm/eyened_orm/commands/ -q
```

Expected: `14 passed` (4 new + the 10 existing `test_targets.py` tests).

- [ ] **Step 5: Confirm `alembic`'s own prompt is untouched**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git diff --stat orm/
sed -n '45,60p' orm/migrations/alembic/env.py
```

Expected: the diff touches only `orm/eyened_orm/commands/shared.py` and the new test file; `env.py` still lists `current` and `heads` among its no-prompt commands (`bootstrap.sh` uses only those two, so `env.py` never needs changing and keeps guarding manual `make migrate` runs).

- [ ] **Step 6: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add orm/eyened_orm/commands/shared.py orm/eyened_orm/commands/test_shared.py
git commit -m "fix(orm): gate eorm confirmation on database state, not on the command

get_database(confirmation=True) prompted unconditionally with a randomly
generated code that cannot be piped, making initialize-database
unautomatable. Prompt only when the target database contains tables:
nothing in these commands can harm an empty one, while stamp_alembic_head
on a populated database silently skips migrations. Failing inspection
falls back to prompting."
```

---

### Task 2: `deploy/` skeleton, env template, and ignore files

Everything later tasks write into, plus the two ignore files that keep generated artifacts and secrets out of git and keep the build context small (both images build from the repo root, so an unfiltered context would ship `dev/.venv`, `node_modules`, and the docs build).

**Files:**
- Create: `deploy/.env.example`, `deploy/storage-mounts.json.example`, `deploy/nginx/storage.d/.gitkeep`, `.dockerignore`
- Modify: `.gitignore`

**Interfaces:**
- Produces: the canonical variable names every later task reads — `COMPOSE_FILE`, `COMPOSE_PROFILES`, `COMPOSE_PROJECT_NAME`, `HTTP_PORT`, `ADMINER_PORT`, `PUBLIC_HOST`, `MYSQL_ROOT_PASSWORD`, `EYENED_DATABASE_{USER,PASSWORD,DATABASE,HOST,PORT}`, `EYENED_REDIS_PASSWORD`, `EYENED_API_SECRET_KEY`, `PLATFORM_STORAGE_PATH`, `DB_PUBLISH_PORT`, `REDIS_PUBLISH_PORT`, `CLIENT_UPSTREAM_PORT`, `KEYCLOAK_PORT`.

- [ ] **Step 1: Create `deploy/.env.example`**

```bash
# deploy/.env.example — copy to deploy/.env (the entry points do this for you).
#
# Working local defaults: ./install.sh and `make up` both work from a clean
# clone with zero edits. The placeholder secrets below are replaced with
# generated values on first run. Never reuse them anywhere reachable.

# ---- Which layers and profiles this stack runs -----------------------------
# COMPOSE_FILE must name EVERY layer: setting it disables compose's automatic
# compose.override.yaml discovery. The entry points rewrite this line.
#
# Developer stack (`make up`):
COMPOSE_FILE=compose.yaml:compose.override.yaml:compose.local-db.yaml:compose.storage.yaml
# Client install (`./install.sh`) — the same minus the dev override, plus prod:
# COMPOSE_FILE=compose.yaml:compose.local-db.yaml:compose.storage.yaml:compose.prod.yaml
#
# 'local-db' runs the bundled MySQL. It must agree with compose.local-db.yaml
# in COMPOSE_FILE above — `make doctor` checks that it does.
# Add 'oidc' to run the bundled Keycloak (development OIDC).
COMPOSE_PROFILES=local-db

# ---- This stack's identity on a shared host --------------------------------
# On a machine shared with other developers, make these unique (for example
# eyened-yourname) so containers, volumes and ports do not collide.
COMPOSE_PROJECT_NAME=eyened
# Port the platform is served on — this is the URL you open in a browser.
HTTP_PORT=8080
# Port for adminer (bundled database browser, runs with the local-db profile).
ADMINER_PORT=8081
# Hostname or IP you type in the browser. Only required for OIDC redirects.
PUBLIC_HOST=localhost

# ---- Bundled database ------------------------------------------------------
# Replaced with generated values on first run.
MYSQL_ROOT_PASSWORD=change_me
EYENED_DATABASE_USER=eyened
EYENED_DATABASE_PASSWORD=change_me
EYENED_DATABASE_DATABASE=eyened_database
# Where the server looks for MySQL. 'database' is the bundled container.
EYENED_DATABASE_HOST=database
EYENED_DATABASE_PORT=3306
#
# To use an EXTERNAL database instead:
#   1. remove 'local-db' from COMPOSE_PROFILES above
#   2. remove compose.local-db.yaml from COMPOSE_FILE above
#   3. point EYENED_DATABASE_* at that server
# Bootstrap then declines to touch it.
#
# The bundled MySQL publishes NO host port by default — that is the single
# biggest source of collisions between developers on one machine. For DBeaver
# or a host-side alembic, append :compose.host-ports.yaml to COMPOSE_FILE and
# pick values nobody else is using:
# DB_PUBLISH_PORT=13306
# REDIS_PUBLISH_PORT=16379

# ---- Redis -----------------------------------------------------------------
EYENED_REDIS_PASSWORD=change_me

# ---- API -------------------------------------------------------------------
# Session/JWT signing key, generated on first run. Never copy a key between
# deployments — every stack must have its own.
EYENED_API_SECRET_KEY=
EYENED_API_PUBLIC_AUTH_DISABLED=false
EYENED_API_DEBUG=false
#
# Only for hosts that read image files through the API instead of from disk
# (notebooks, remote workers). The server in this stack reads them locally.
# EYENED_API_URL=http://localhost:8080/api
# EYENED_API_USERNAME=
# EYENED_API_PASSWORD=

# ---- Storage ---------------------------------------------------------------
# Platform storage (thumbnails + segmentations.zarr) is ALWAYS /storage inside
# the container. By default that is this stack's own named volume, so a clean
# clone writes nothing outside itself and never touches production data.
# Opt in to shared/production platform storage with an absolute host path:
# PLATFORM_STORAGE_PATH=/mnt/oogergo/eyened/eyened_platform
#
# Image datasets are NOT configured here. They live in storage-mounts.json,
# from which the container mounts, the nginx routes, and EYENED_STORAGE_MOUNTS
# are all generated. See deploy/README.md.
```

- [ ] **Step 2: Create `deploy/storage-mounts.json.example`**

Empty by design: a fresh bundled database has no `StorageBackend` rows, so a clean clone configures no mounts. `deploy/README.md` (Task 14) shows the populated shape.

```json
{
}
```

- [ ] **Step 3: Create `deploy/nginx/storage.d/.gitkeep`**

The directory must exist in a clean clone because `compose.yaml` mounts it into nginx and `storage.conf` is generated. Empty file.

- [ ] **Step 4: Create the root `.dockerignore`**

Both images use the repo root as build context. Without this the context includes the venv, `node_modules`, and the docs build.

```
.git
.github
**/.venv
**/node_modules
**/__pycache__
**/*.pyc
**/.pytest_cache
**/.ipynb_checkpoints
client/.svelte-kit
client/build
docs/dist
docs/.astro
graphify-out
notebooks
worker
dev
docker
database
deploy
*.zip
```

Note: `deploy` is excluded from the *context* for the server and client images, which copy only `orm/`, `server/`, and `client/`. `Dockerfile.client`'s dev stage needs `deploy/entrypoint-client.sh`, so Task 3 adds a negation for that one file.

- [ ] **Step 5: Update the root `.gitignore`**

Remove the two lines for stacks this change supersedes and add the `deploy/` entries. Delete:

```
docker/.env
dev/docker-compose.yml
```

Append:

```
# deploy/ — secrets and generated artifacts
deploy/.env
deploy/.env.*
!deploy/.env.example
deploy/storage-mounts.json
deploy/compose.storage.yaml
deploy/nginx/storage.d/*.conf
deploy/snapshots/
```

`deploy/.env` is already matched by the existing `*.env` line; the explicit entry documents intent and the negation protects `.env.example` from the `deploy/.env.*` pattern.

- [ ] **Step 6: Verify the ignore rules do what they claim**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
printf 'x' > deploy/.env
printf 'x' > deploy/compose.storage.yaml
printf 'x' > deploy/nginx/storage.d/storage.conf
git check-ignore -v deploy/.env deploy/compose.storage.yaml deploy/nginx/storage.d/storage.conf
git check-ignore deploy/.env.example || echo "OK: .env.example is tracked"
rm -f deploy/.env deploy/compose.storage.yaml deploy/nginx/storage.d/storage.conf
```

Expected: the three paths each print a matching `.gitignore` rule; `.env.example` prints `OK: .env.example is tracked`.

- [ ] **Step 7: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add deploy/.env.example deploy/storage-mounts.json.example \
        deploy/nginx/storage.d/.gitkeep .dockerignore .gitignore
git commit -m "feat(deploy): env template, storage-mounts template, ignore rules"
```

---

### Task 3: Unified Dockerfiles

`dev/Dockerfile.server` and `docker/Dockerfile.server` are byte-identical except for a trailing `CMD` — and the prod file carries a **dead** first `CMD` (Docker keeps only the last), so its `uvicorn --reload` line has never run. `dev/Dockerfile.client` and `docker/Dockerfile.client` differ only dev-vs-prod. Collapse each pair into one file; the run command moves into compose.

**Files:**
- Create: `deploy/Dockerfile.server`, `deploy/Dockerfile.client`, `deploy/entrypoint-client.sh`
- Modify: `.dockerignore` (negation for the client entrypoint)

**Interfaces:**
- Consumes: build context = repo root (`context: ..` from `deploy/`).
- Produces: server image with default CMD **gunicorn** (compose's dev override replaces it with `uvicorn --reload`); client image with build targets **`dev`** (vite on 5173) and **`prod`** (built preview on 4173). `compose.yaml` (Task 7) selects `target: prod`; `compose.override.yaml` (Task 8) selects `target: dev`.

- [ ] **Step 1: Create `deploy/Dockerfile.server`**

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY orm /app/orm
RUN pip install -e /app/orm

COPY server /app/server
RUN pip install --no-cache-dir -r /app/server/requirements.txt

EXPOSE 8000

WORKDIR /app

# One image, two run commands. This default is the production one; the dev
# compose layer replaces it with `uvicorn --reload` over bind-mounted sources.
# Shell form so ${WORKERS} is expanded at runtime.
CMD gunicorn server.main:app \
    --workers ${WORKERS:-4} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --log-level ${LOG_LEVEL:-info} \
    --access-logfile - \
    --error-logfile -
```

- [ ] **Step 2: Move the client entrypoint and create `deploy/Dockerfile.client`**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git mv dev/entrypoint-client.sh deploy/entrypoint-client.sh
```

`deploy/Dockerfile.client`:

```dockerfile
# Shared base: everything both environments need.
FROM node:24-slim AS base
COPY client /app/client
WORKDIR /app/client
RUN npm install

# Development: vite dev server with hot reload over a bind-mounted source tree.
FROM base AS dev
COPY deploy/entrypoint-client.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 5173
ENTRYPOINT ["/entrypoint.sh"]

# Production: build once, serve the built output.
FROM base AS prod
RUN npm run build
EXPOSE 4173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4173"]
```

- [ ] **Step 3: Let the client entrypoint through `.dockerignore`**

Add immediately after the `deploy` line:

```
deploy
!deploy/entrypoint-client.sh
```

- [ ] **Step 4: Build both images and both client targets**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
docker build -f deploy/Dockerfile.server -t eyened-server-check .
docker build -f deploy/Dockerfile.client --target dev  -t eyened-client-dev-check  .
docker build -f deploy/Dockerfile.client --target prod -t eyened-client-prod-check .
```

Expected: three successful builds.

- [ ] **Step 5: Verify the server image defaults to gunicorn and the ORM is importable**

```bash
docker inspect -f '{{join .Config.Cmd " "}}' eyened-server-check
docker run --rm eyened-server-check python -c "import eyened_orm, server; print('imports ok')"
```

Expected: the `Cmd` contains `gunicorn` and no `--reload`; the second command prints `imports ok`.

- [ ] **Step 6: Verify the prod client target really built the app**

```bash
docker run --rm eyened-client-prod-check sh -c 'ls .svelte-kit/output/client >/dev/null && echo "build output present"'
docker run --rm --entrypoint sh eyened-client-dev-check -c 'test -x /entrypoint.sh && echo "dev entrypoint present"'
```

Expected: `build output present` and `dev entrypoint present`. (If the SvelteKit adapter writes elsewhere, adjust the path to whatever `npm run build` produces — the point of the check is that the prod stage ran the build and the dev stage did not.)

- [ ] **Step 7: Clean up and commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
docker image rm eyened-server-check eyened-client-dev-check eyened-client-prod-check
git add deploy/Dockerfile.server deploy/Dockerfile.client deploy/entrypoint-client.sh .dockerignore
git add -u dev/entrypoint-client.sh
git commit -m "feat(deploy): unify the server and client Dockerfiles

One server image (the prod file's first CMD was dead — Docker keeps only
the last) with the run command moved to compose, and one multi-stage
client image with dev and prod targets."
```

---

### Task 4: nginx template with a generated-locations include

One template replaces `dev/nginx.conf` and `docker/nginx.conf`, whose only real difference is the client upstream port. Per-backend `location` blocks stop being hand-edited and become a generated include.

The include must **not** live in `conf.d/`: the stock image includes `/etc/nginx/conf.d/*.conf` inside the `http{}` block, and `20-envsubst-on-templates.sh` renders templates into that same directory, so a bare `location` there is a startup failure (`nginx: [emerg] "location" directive is not allowed here` — verified). It goes in `/etc/nginx/storage.d/` and is included from inside `server{}`.

**Files:**
- Create: `deploy/nginx/default.conf.template`

**Interfaces:**
- Consumes: `CLIENT_UPSTREAM_PORT` from the container environment (nginx's own envsubst substitutes it); `/etc/nginx/storage.d/*.conf` produced by Task 6; `/storage/thumbnails/` from the platform storage mount.
- Produces: the nginx config that `compose.yaml` mounts as `/etc/nginx/templates/default.conf.template`.

- [ ] **Step 1: Create `deploy/nginx/default.conf.template`**

```nginx
server {
    listen 80;
    resolver 127.0.0.11 valid=10s;
    client_max_body_size 120M;
    sendfile on;
    gzip on;
    gzip_types text/plain application/json application/octet-stream;
    gzip_vary on;
    gunzip on;
    access_log off;

    # API
    location /api/ {
        proxy_pass http://server:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend. ${CLIENT_UPSTREAM_PORT} is 5173 (vite dev server) or 4173
    # (built preview) — the only thing that used to differ between the dev
    # and prod nginx configs.
    location / {
        proxy_pass http://client:${CLIENT_UPSTREAM_PORT};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Vite HMR needs the websocket upgrade; harmless for the built preview.
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $http_connection;
        proxy_cache_bypass $http_upgrade;
        proxy_buffering off;
    }

    # Platform thumbnails. EYENED_STORAGE_ROOT is always /storage inside the
    # container; the API sends X-Accel-Redirect: /thumbnails/<path>.
    location /thumbnails/ {
        internal;
        # the trailing slash on alias matters
        alias /storage/thumbnails/;
    }

    # Per-StorageBackend locations, generated from storage-mounts.json by
    # deploy/scripts/gen-storage.sh. Deliberately NOT in conf.d/, which the
    # base image includes inside http{} where a location block is illegal.
    # A glob that matches nothing is valid nginx, so a clean clone with no
    # datasets still passes `nginx -t`.
    include /etc/nginx/storage.d/*.conf;
}
```

- [ ] **Step 2: Verify the empty case — a clean clone with no datasets**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
docker run --rm \
  -e CLIENT_UPSTREAM_PORT=4173 \
  -v "$PWD/deploy/nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro" \
  -v "$PWD/deploy/nginx/storage.d:/etc/nginx/storage.d:ro" \
  nginx:1.27-alpine nginx -t
```

Expected: `nginx: configuration file /etc/nginx/nginx.conf test is successful`.

- [ ] **Step 3: Verify the populated case, and that the port really was substituted**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
mkdir -p /tmp/storage.d-probe
cat > /tmp/storage.d-probe/storage.conf <<'EOF'
location /probe/ {
    internal;
    alias /mnt/probe/;
}
EOF
docker run --rm \
  -e CLIENT_UPSTREAM_PORT=5173 \
  -v "$PWD/deploy/nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro" \
  -v "/tmp/storage.d-probe:/etc/nginx/storage.d:ro" \
  nginx:1.27-alpine sh -c '/docker-entrypoint.sh nginx -t && grep -n "proxy_pass http://client" /etc/nginx/conf.d/default.conf'
rm -rf /tmp/storage.d-probe
```

Expected: the test succeeds and the grep prints `proxy_pass http://client:5173;` — proving envsubst replaced `${CLIENT_UPSTREAM_PORT}` while leaving nginx's own `$host`/`$uri` variables alone.

- [ ] **Step 4: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add deploy/nginx/default.conf.template
git commit -m "feat(deploy): one nginx template with a generated storage.d include

Client upstream port becomes \${CLIENT_UPSTREAM_PORT}; per-backend
locations move out of the hand-edited config into an include outside
conf.d/, where a bare location block would be a startup failure."
```

---

### Task 5: Shared shell library and compose-binary resolution

The spec requires that "the shared first-run logic lives in one place so the two entry points cannot drift." This is that place. Everything else in `deploy/scripts/` sources it.

**Files:**
- Create: `deploy/scripts/lib.sh`, `deploy/scripts/compose-bin.sh`

**Spec note:** the spec's file list does not name `lib.sh`/`compose-bin.sh`; they exist to satisfy its "one place" requirement, and because Make cannot source a shell library, the Makefile needs a command that prints the resolved binary.

**Interfaces:**
- Consumes: `REPO_ROOT`, which every caller sets before sourcing.
- Produces, for all later tasks:
  - variables `DEPLOY_DIR`, `COMPOSE_BIN`, `COMPOSE_FILE_DEV`, `COMPOSE_FILE_CLIENT`
  - functions `die MSG`, `resolve_compose`, `compose ARGS...`, `gen_secret`, `gen_password`, `env_get KEY [FILE]`, `env_set KEY VALUE [FILE]`, `first_run_env dev|client`, `print_day2`

- [ ] **Step 1: Create `deploy/scripts/lib.sh`**

```sh
# Shared helpers for the deploy entry points. POSIX sh — no bashisms.
# Sourced, never executed. Callers set REPO_ROOT first:
#
#   REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
#   . "$REPO_ROOT/deploy/scripts/lib.sh"

: "${REPO_ROOT:?lib.sh: set REPO_ROOT before sourcing}"
DEPLOY_DIR="$REPO_ROOT/deploy"

# The two layer lists. COMPOSE_FILE must name every layer: setting it disables
# compose's automatic compose.override.yaml discovery.
COMPOSE_FILE_DEV="compose.yaml:compose.override.yaml:compose.local-db.yaml:compose.storage.yaml"
COMPOSE_FILE_CLIENT="compose.yaml:compose.local-db.yaml:compose.storage.yaml:compose.prod.yaml"

die() {
    printf '%s\n' "$*" >&2
    exit 1
}

# Resolve the compose binary once. This host has no `docker compose` plugin,
# only the standalone binary — so nothing may hardcode either form, including
# the commands we print for the operator to run later.
resolve_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_BIN="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_BIN="docker-compose"
    else
        die "error: neither 'docker compose' nor 'docker-compose' is available.
      Fix: install Docker — https://docs.docker.com/get-docker/"
    fi
}

# Run compose from deploy/, where .env and the layer files live.
# $COMPOSE_BIN is deliberately unquoted: "docker compose" must split in two.
compose() {
    ( cd "$DEPLOY_DIR" && $COMPOSE_BIN "$@" )
}

# A signing key must never be copied from a template — that would give every
# deployment the same JWT key. Two sources, and a hard failure if neither is
# present: an empty signing key is far worse than a refusal to start.
gen_secret() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import secrets; print(secrets.token_hex(32))'
    else
        die "error: need 'openssl' or 'python3' to generate a signing key, and
      neither is installed. Install either one and re-run."
    fi
}

gen_password() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 12
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import secrets; print(secrets.token_hex(12))'
    else
        die "error: need 'openssl' or 'python3' to generate a password, and
      neither is installed. Install either one and re-run."
    fi
}

# Read a value from an env file. Last assignment wins; values are taken
# verbatim, which is what compose does too.
env_get() {
    _file=${2:-$DEPLOY_DIR/.env}
    [ -f "$_file" ] || return 0
    sed -n "s/^[[:space:]]*$1=//p" "$_file" | tail -n 1
}

# Write a value into an env file, replacing any existing assignment.
# `sed -i` is not portable (GNU takes no argument, BSD requires one), so this
# writes a temp file and moves it.
env_set() {
    _key=$1
    _val=$2
    _file=${3:-$DEPLOY_DIR/.env}
    _tmp="$_file.tmp.$$"
    if grep -q "^[[:space:]]*$_key=" "$_file" 2>/dev/null; then
        sed "s|^[[:space:]]*$_key=.*|$_key=$_val|" "$_file" > "$_tmp"
    else
        cat "$_file" > "$_tmp" 2>/dev/null || :
        printf '%s=%s\n' "$_key" "$_val" >> "$_tmp"
    fi
    mv "$_tmp" "$_file"
}

# First-run setup, shared by ./install.sh and deploy/scripts/up.sh so the two
# entry points cannot drift. MODE is dev or client and decides which layer
# list is recorded — that one line is what lets every later command be a bare
# `docker compose ...` with no -f flags.
first_run_env() {
    _mode=$1
    if [ ! -f "$DEPLOY_DIR/.env" ]; then
        cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
        env_set EYENED_API_SECRET_KEY "$(gen_secret)"
        env_set EYENED_REDIS_PASSWORD "$(gen_secret)"
        env_set MYSQL_ROOT_PASSWORD "$(gen_password)"
        env_set EYENED_DATABASE_PASSWORD "$(gen_password)"
        echo "==> created deploy/.env with generated secrets"
        echo "    On a shared machine, set COMPOSE_PROJECT_NAME and HTTP_PORT"
        echo "    in deploy/.env to something nobody else is using."
    fi

    case "$_mode" in
        dev)    env_set COMPOSE_FILE "$COMPOSE_FILE_DEV" ;;
        client) env_set COMPOSE_FILE "$COMPOSE_FILE_CLIENT" ;;
        *)      die "first_run_env: expected 'dev' or 'client', got '$_mode'" ;;
    esac

    [ -f "$DEPLOY_DIR/storage-mounts.json" ] || \
        cp "$DEPLOY_DIR/storage-mounts.json.example" "$DEPLOY_DIR/storage-mounts.json"
}

# The day-2 commands, printed with the binary THIS host actually has. Naming
# the wrong one recreates exactly the failure resolve_compose exists to avoid.
print_day2() {
    _host=$(env_get PUBLIC_HOST)
    _port=$(env_get HTTP_PORT)
    cat <<EOF

========================================================================
The platform is running.

  Open:  http://${_host:-localhost}:${_port:-8080}/

Day-to-day commands — run them from the deploy/ directory. No make and no
-f flags: the install recorded which layers this stack uses.

  cd $DEPLOY_DIR
  $COMPOSE_BIN logs -f
  $COMPOSE_BIN down
  $COMPOSE_BIN up -d
========================================================================
EOF
}
```

- [ ] **Step 2: Create `deploy/scripts/compose-bin.sh`**

```sh
#!/bin/sh
# Print the compose binary this host has. The Makefile cannot source lib.sh,
# so it calls this instead of hardcoding either form.
set -eu
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose
printf '%s\n' "$COMPOSE_BIN"
```

- [ ] **Step 3: Make the script executable and check it resolves this host correctly**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
chmod +x deploy/scripts/compose-bin.sh
deploy/scripts/compose-bin.sh
```

Expected: `docker-compose` on this host (no plugin installed).

- [ ] **Step 4: Check the library's helpers behave**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
sh -c '
set -eu
REPO_ROOT=$PWD
. deploy/scripts/lib.sh
tmp=$(mktemp)
printf "A=1\nB=2\n" > "$tmp"
env_set A 99 "$tmp"
env_set C new "$tmp"
echo "A=$(env_get A "$tmp") B=$(env_get B "$tmp") C=$(env_get C "$tmp")"
s1=$(gen_secret); s2=$(gen_secret)
[ "$s1" != "$s2" ] && echo "secrets differ (${#s1} chars)"
rm -f "$tmp"
'
```

Expected: `A=99 B=2 C=new` then `secrets differ (64 chars)`.

- [ ] **Step 5: Verify the secret-generation fallbacks, including the hard failure**

A silent empty signing key is far worse than a refusal to start, so both fallbacks matter. Run each in a `PATH` containing only what the branch under test is allowed to see:

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
mkdir -p /tmp/nopath/bin
for tool in sh sed grep tr cat mktemp printf awk; do
    p=$(command -v "$tool" 2>/dev/null) && ln -sf "$p" /tmp/nopath/bin/ || true
done

# python3 only (no openssl)
ln -sf "$(command -v python3)" /tmp/nopath/bin/
env PATH=/tmp/nopath/bin sh -c 'REPO_ROOT='"$PWD"'; . deploy/scripts/lib.sh; k=$(gen_secret); echo "python3 fallback: ${#k} chars"'

# neither: must fail loudly
rm -f /tmp/nopath/bin/python3
env PATH=/tmp/nopath/bin sh -c 'REPO_ROOT='"$PWD"'; . deploy/scripts/lib.sh; gen_secret'; echo "exit=$?"
rm -rf /tmp/nopath
```

Expected: `python3 fallback: 64 chars`; then an error naming both tools and `exit=1` — never an empty line and a zero exit.

- [ ] **Step 6: Check POSIX conformance with `dash`**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
command -v dash >/dev/null && dash -n deploy/scripts/lib.sh deploy/scripts/compose-bin.sh && echo "dash: syntax ok"
```

Expected: `dash: syntax ok`. (If `dash` is absent, run the same check inside a container: `docker run --rm -v "$PWD:/w" -w /w alpine sh -n deploy/scripts/lib.sh`.) Repeat this check for every script added in later tasks.

- [ ] **Step 7: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add deploy/scripts/lib.sh deploy/scripts/compose-bin.sh
git commit -m "feat(deploy): shared POSIX sh helpers and compose binary resolution"
```

---

### Task 6: `gen-storage.sh` — one source of truth for storage mounts

Today each backend key costs three edits that must agree: a compose bind mount, an nginx `location`, and an `EYENED_STORAGE_MOUNTS` entry. This generates all three from `deploy/storage-mounts.json`.

Both outputs are written **every** time, even with no mounts, because `COMPOSE_FILE` names `compose.storage.yaml` and a missing file breaks compose before any entry point runs.

**Files:**
- Create: `deploy/scripts/gen-storage.sh`

**Interfaces:**
- Consumes: `deploy/storage-mounts.json` (flat `{"key": "/abs/path"}`); `lib.sh` for `die`/`DEPLOY_DIR`.
- Produces: `deploy/compose.storage.yaml` (bind mounts on `server` and `fileserver`, plus `EYENED_STORAGE_MOUNTS` on `server`) and `deploy/nginx/storage.d/storage.conf` (one `internal` location per key). Both gitignored.

**Spec note on the empty case:** `is_local_storage_enabled()` (`orm/eyened_orm/data_access.py:61-63`) treats **any** non-empty `EYENED_STORAGE_MOUNTS` string as "local mode on" — including `'{}'`. So with no mounts configured the generator emits **no** `EYENED_STORAGE_MOUNTS` key at all, leaving the ORM on its API adapter rather than putting it in local mode with nothing to resolve. `services: {}` as the whole file is valid at compose 2.15 and merges cleanly (verified).

- [ ] **Step 1: Create `deploy/scripts/gen-storage.sh`**

```sh
#!/bin/sh
# Generate every storage artifact from deploy/storage-mounts.json:
#
#   deploy/compose.storage.yaml          bind mounts + EYENED_STORAGE_MOUNTS
#   deploy/nginx/storage.d/storage.conf  one internal nginx location per key
#
# Both are always written, even with no mounts: COMPOSE_FILE names
# compose.storage.yaml, so a missing file breaks compose before make runs.
#
# storage-mounts.json is a FLAT object of "key": "/absolute/path" pairs.
# Keys and paths may not contain " , ' or $ — anything that does not parse is
# an error, never a silently dropped mount.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"

SRC="$DEPLOY_DIR/storage-mounts.json"
COMPOSE_OUT="$DEPLOY_DIR/compose.storage.yaml"
NGINX_OUT="$DEPLOY_DIR/nginx/storage.d/storage.conf"

[ -f "$SRC" ] || die "error: $SRC not found.
      Fix: cp deploy/storage-mounts.json.example deploy/storage-mounts.json"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Flatten the object to one entry per line.
tr '\n' ' ' < "$SRC" \
    | sed -n 's/^[^{]*{\(.*\)}[^}]*$/\1/p' \
    | tr ',' '\n' \
    | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
    | grep -v '^$' > "$work/entries" || :

: > "$work/mounts"
while IFS= read -r entry; do
    key=$(printf '%s' "$entry" | sed -n 's/^"\([^"]*\)"[[:space:]]*:.*$/\1/p')
    path=$(printf '%s' "$entry" | sed -n 's/^"[^"]*"[[:space:]]*:[[:space:]]*"\([^"]*\)"$/\1/p')

    if [ -z "$key" ] || [ -z "$path" ]; then
        die "error: cannot parse this entry in storage-mounts.json:
        $entry
      It must be a flat JSON object of \"key\": \"/absolute/path\" pairs,
      with no commas or quotes inside keys or paths."
    fi
    case "$path" in
        /*) ;;
        *)  die "error: storage mount \"$key\" must be an absolute host path, got: $path" ;;
    esac
    case "$key$path" in
        *[\'\$]*) die "error: storage mount \"$key\" contains ' or \$, which cannot be
      passed safely through compose. Rename the key or move the directory." ;;
    esac

    printf '%s\t%s\n' "$key" "$path" >> "$work/mounts"
done < "$work/entries"

# --- nginx locations -------------------------------------------------------
{
    echo "# GENERATED by deploy/scripts/gen-storage.sh from storage-mounts.json."
    echo "# Do not edit: your changes will be overwritten on the next run."
    awk -F'\t' '{
        printf "\nlocation /%s/ {\n", $1
        printf "    internal;\n"
        printf "    # the trailing slash on alias matters\n"
        printf "    alias %s/;\n}\n", $2
    }' "$work/mounts"
} > "$work/storage.conf"
mkdir -p "$(dirname "$NGINX_OUT")"
mv "$work/storage.conf" "$NGINX_OUT"

# --- compose overlay -------------------------------------------------------
if [ -s "$work/mounts" ]; then
    json=$(awk -F'\t' '{printf "%s\"%s\":\"%s\"", (NR > 1 ? "," : ""), $1, $2}' "$work/mounts")
    {
        echo "# GENERATED by deploy/scripts/gen-storage.sh from storage-mounts.json."
        echo "# Do not edit: your changes will be overwritten on the next run."
        echo "services:"
        echo "  server:"
        echo "    environment:"
        echo "      EYENED_STORAGE_MOUNTS: '{$json}'"
        echo "    volumes:"
        awk -F'\t' '{printf "      - %s:%s:ro\n", $2, $2}' "$work/mounts"
        echo "  fileserver:"
        echo "    volumes:"
        awk -F'\t' '{printf "      - %s:%s:ro\n", $2, $2}' "$work/mounts"
    } > "$work/compose.storage.yaml"
else
    {
        echo "# GENERATED by deploy/scripts/gen-storage.sh — no storage mounts configured."
        echo "# EYENED_STORAGE_MOUNTS is deliberately absent rather than '{}': any"
        echo "# non-empty value switches the ORM into local mode, and local mode with"
        echo "# nothing to resolve is worse than the API adapter it replaces."
        echo "services: {}"
    } > "$work/compose.storage.yaml"
fi
mv "$work/compose.storage.yaml" "$COMPOSE_OUT"

count=$(wc -l < "$work/mounts" | tr -d ' ')
echo "==> generated compose.storage.yaml and nginx/storage.d/storage.conf ($count mount(s))"
```

- [ ] **Step 2: Run it against the empty template**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
chmod +x deploy/scripts/gen-storage.sh
cp deploy/storage-mounts.json.example deploy/storage-mounts.json
deploy/scripts/gen-storage.sh
cat deploy/compose.storage.yaml
cat deploy/nginx/storage.d/storage.conf
```

Expected: `==> generated ... (0 mount(s))`; `compose.storage.yaml` ends in `services: {}` with no `EYENED_STORAGE_MOUNTS`; `storage.conf` is header comments only.

- [ ] **Step 3: Run it against two real keys**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
cat > deploy/storage-mounts.json <<'EOF'
{
  "oogergo": "/mnt/oogergo",
  "genr": "/mnt/genr"
}
EOF
deploy/scripts/gen-storage.sh
cat deploy/compose.storage.yaml
cat deploy/nginx/storage.d/storage.conf
```

Expected `compose.storage.yaml` body:

```yaml
services:
  server:
    environment:
      EYENED_STORAGE_MOUNTS: '{"oogergo":"/mnt/oogergo","genr":"/mnt/genr"}'
    volumes:
      - /mnt/oogergo:/mnt/oogergo:ro
      - /mnt/genr:/mnt/genr:ro
  fileserver:
    volumes:
      - /mnt/oogergo:/mnt/oogergo:ro
      - /mnt/genr:/mnt/genr:ro
```

Expected `storage.conf` body: two blocks, `location /oogergo/ { internal; alias /mnt/oogergo/; }` and the same for `genr`.

- [ ] **Step 4: Verify the generated nginx conf actually loads**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
docker run --rm \
  -e CLIENT_UPSTREAM_PORT=4173 \
  -v "$PWD/deploy/nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro" \
  -v "$PWD/deploy/nginx/storage.d:/etc/nginx/storage.d:ro" \
  nginx:1.27-alpine nginx -t
```

Expected: `test is successful`.

- [ ] **Step 5: Verify malformed input is rejected, not silently dropped**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
printf '{"relative": "not/absolute"}\n' > deploy/storage-mounts.json
deploy/scripts/gen-storage.sh; echo "exit=$?"
printf '{"broken": }\n' > deploy/storage-mounts.json
deploy/scripts/gen-storage.sh; echo "exit=$?"
cp deploy/storage-mounts.json.example deploy/storage-mounts.json
deploy/scripts/gen-storage.sh
```

Expected: the first two runs print an error naming the offending key and `exit=1`; the third succeeds with 0 mounts.

- [ ] **Step 6: Syntax check and commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
docker run --rm -v "$PWD:/w" -w /w alpine sh -n deploy/scripts/gen-storage.sh && echo "sh: syntax ok"
git add deploy/scripts/gen-storage.sh
git commit -m "feat(deploy): generate compose mounts, nginx locations and EYENED_STORAGE_MOUNTS

storage-mounts.json becomes the single source of truth for the three
places a StorageBackend key had to be repeated by hand."
```

---

### Task 7: `compose.yaml` — the base stack

Every service, production-ready defaults, no dev assumptions. The bundled database and adminer sit behind a `local-db` profile; Keycloak arrives in Task 13; the backup service in Task 12.

**Files:**
- Create: `deploy/compose.yaml`

**Interfaces:**
- Consumes: `deploy/.env` (compose reads it automatically for interpolation, and services declare `env_file: .env` to get variables *into* containers); the Dockerfiles from Task 3; the nginx template from Task 4.
- Produces: services `database`, `adminer`, `redis`, `server`, `client`, `fileserver`; volumes `db_data`, `platform_storage`, `client_node_modules`; profile `local-db`.

**Design notes carried from the spec:**
- `server → database` `depends_on` must **not** live here. If an always-on `server` declared a dependency on a profile-gated `database`, turning the profile off for an external database would make compose refuse to start. It goes in `compose.local-db.yaml` (Task 8).
- `${PLATFORM_STORAGE_PATH:-platform_storage}` is a deliberate trick: unset, the mount source is the *named volume* `platform_storage`; set to an absolute path, it is a bind mount. That is what makes a clean clone write nothing outside its own stack and what makes Docker Desktop work with no special case.
- The MySQL healthcheck is a **liveness** signal only. `mysqladmin ping` reports success even when credentials are rejected, and a password passed inline would be visible in `ps`.

- [ ] **Step 1: Create `deploy/compose.yaml`**

```yaml
# Base stack: the whole service graph with production-ready defaults.
#
# No `name:` — the project name comes from COMPOSE_PROJECT_NAME in .env, which
# is what lets several developers run isolated stacks on one machine.
#
# Layers on top of this: compose.override.yaml (dev), compose.local-db.yaml
# (bundled database), compose.prod.yaml (deployments), compose.storage.yaml
# (generated). COMPOSE_FILE in .env names the ones in play.

services:

  database:
    profiles: ["local-db"]
    image: mysql:8.0.27
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:?set MYSQL_ROOT_PASSWORD in deploy/.env}
      MYSQL_DATABASE: ${EYENED_DATABASE_DATABASE:-eyened_database}
      MYSQL_USER: ${EYENED_DATABASE_USER:?set EYENED_DATABASE_USER in deploy/.env}
      MYSQL_PASSWORD: ${EYENED_DATABASE_PASSWORD:?set EYENED_DATABASE_PASSWORD in deploy/.env}
    volumes:
      - db_data:/var/lib/mysql
    # Liveness only: mysqladmin ping answers even when credentials are
    # rejected, and a password on the command line would show up in `ps`.
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 30s
    # No host port by default — see compose.host-ports.yaml.

  adminer:
    profiles: ["local-db"]
    image: adminer:4.8.1
    ports:
      - "${ADMINER_PORT:-8081}:8080"
    environment:
      ADMINER_DEFAULT_SERVER: database

  redis:
    image: redis:7-alpine
    environment:
      REDIS_PASSWORD: ${EYENED_REDIS_PASSWORD:?set EYENED_REDIS_PASSWORD in deploy/.env}
    command: >
      sh -c 'exec redis-server --requirepass "$$REDIS_PASSWORD"'
    healthcheck:
      test: ["CMD-SHELL", 'redis-cli -a "$$REDIS_PASSWORD" ping | grep -q PONG']
      interval: 5s
      timeout: 3s
      retries: 5
    # No host port by default — see compose.host-ports.yaml.

  server:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.server
    env_file: .env
    environment:
      EYENED_REDIS_HOST: redis
      EYENED_REDIS_PORT: "6379"
      EYENED_REDIS_PASSWORD: ${EYENED_REDIS_PASSWORD:?}
      EYENED_DATABASE_HOST: ${EYENED_DATABASE_HOST:-database}
      # Always /storage inside the container; what backs it is decided below.
      EYENED_STORAGE_ROOT: /storage
      # OIDC endpoints are browser-facing, so they are built from PUBLIC_HOST.
      # Inert unless EYENED_API_AUTH_OIDC_ENABLED is true (see the oidc profile).
      EYENED_OIDC_METADATA_URL: http://${PUBLIC_HOST:-localhost}:${KEYCLOAK_PORT:-8180}/realms/eyened-dev/.well-known/openid-configuration
      EYENED_OIDC_REDIRECT_URL: http://${PUBLIC_HOST:-localhost}:${HTTP_PORT:-8080}/users/oidc-callback
      EYENED_OIDC_ADDITIONAL_TOKEN_VALIDATIONS: iss=http://${PUBLIC_HOST:-localhost}:${KEYCLOAK_PORT:-8180}/realms/eyened-dev
    volumes:
      # Unset PLATFORM_STORAGE_PATH -> the named volume below (a clean clone
      # writes nothing outside its own stack). Set to an absolute host path ->
      # a bind mount onto shared or production platform storage.
      - ${PLATFORM_STORAGE_PATH:-platform_storage}:/storage
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2).read()
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 20s

  client:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.client
      target: prod

  fileserver:
    image: nginx:1.27-alpine
    env_file: .env
    environment:
      # 4173 = built preview (prod). The dev layer sets 5173 (vite).
      CLIENT_UPSTREAM_PORT: ${CLIENT_UPSTREAM_PORT:-4173}
    ports:
      - "${HTTP_PORT:-8080}:80"
    volumes:
      - ./nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro
      # Always mounted: an empty directory is valid, and the include glob in
      # the template tolerates matching nothing.
      - ./nginx/storage.d:/etc/nginx/storage.d:ro
      # Thumbnails are served straight off platform storage.
      - ${PLATFORM_STORAGE_PATH:-platform_storage}:/storage:ro
    depends_on:
      server:
        condition: service_healthy
      client:
        condition: service_started

volumes:
  db_data:
  platform_storage:
  client_node_modules:
```

- [ ] **Step 2: Create a scratch `.env` and verify the base alone resolves**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation/deploy
cp .env.example .env
sed -i 's/^COMPOSE_FILE=.*/COMPOSE_FILE=compose.yaml/' .env
docker-compose config --services
```

Expected (profile `local-db` is on, so all six appear): `adminer`, `client`, `database`, `fileserver`, `redis`, `server`.

- [ ] **Step 3: Verify the storage default really is the named volume**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation/deploy
docker-compose config | grep -A 4 -E '^\s+volumes:' | head -30
```

Expected: the `server` and `fileserver` volume sources are `platform_storage` (a named volume), not a host path.

Then confirm the opt-in flips it to a bind mount:

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation/deploy
PLATFORM_STORAGE_PATH=/tmp/platform-probe docker-compose config | grep -c '/tmp/platform-probe'
```

Expected: `2` (server read-write, fileserver read-only).

- [ ] **Step 4: Verify the external-database case does not break on a dangling dependency**

This is why `depends_on` is not in the base. With the profile off there is no `database` service:

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation/deploy
COMPOSE_PROFILES= docker-compose config --services
```

Expected: `client`, `fileserver`, `redis`, `server` — no `database`, no `adminer`, and **no error**.

- [ ] **Step 5: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add deploy/compose.yaml
git commit -m "feat(deploy): base compose stack with a local-db profile

All services in one file with prod-ready defaults and pinned images.
Platform storage defaults to a named volume; the bundled database is
profile-gated and publishes no host port."
```

---

### Task 8: The dev, local-db, prod, and host-ports layers

Four small files, each with one job. The awkward part is deliberate and documented: "use the bundled database" is expressed **twice** — `local-db` in `COMPOSE_PROFILES` *and* `compose.local-db.yaml` in `COMPOSE_FILE` — because a compose file layer is merged unconditionally and cannot itself be profile-gated. Task 9's `doctor` turns that footgun into a checked invariant.

**Files:**
- Create: `deploy/compose.override.yaml`, `deploy/compose.local-db.yaml`, `deploy/compose.prod.yaml`, `deploy/compose.host-ports.yaml`

**Interfaces:**
- Consumes: services defined in `compose.yaml` (Task 7); build target `dev` from `Dockerfile.client` (Task 3).
- Produces: the layers `COMPOSE_FILE_DEV` and `COMPOSE_FILE_CLIENT` in `lib.sh` name, plus the optional host-ports layer referenced by `.env.example`.

**Spec note:** the spec says a developer who wants host access to MySQL "uncomments `DB_PUBLISH_PORT`". Compose cannot publish a port conditionally on a variable being set — an entry like `"${DB_PUBLISH_PORT:-3306}:3306"` always publishes, which is the collision the spec is trying to prevent. So the mechanism is an optional **layer**, `compose.host-ports.yaml`, appended to `COMPOSE_FILE`. Same intent, and consistent with layers being explicit everywhere else.

- [ ] **Step 1: Create `deploy/compose.override.yaml` (dev)**

```yaml
# Development layer. Named explicitly in COMPOSE_FILE — setting COMPOSE_FILE
# at all disables compose's automatic discovery of this file, so it is never
# picked up implicitly.

services:

  server:
    # Replaces the image's gunicorn CMD.
    command: >
      uvicorn server.main:app --host 0.0.0.0 --port 8000
      --reload --reload-dir /app/server --reload-dir /app/orm
    volumes:
      - ../server:/app/server
      - ../orm:/app/orm
    environment:
      EYENED_API_DEBUG: "true"
    extra_hosts:
      # Lets the server reach a Keycloak published on the host (oidc profile).
      - "${PUBLIC_HOST:-localhost}:host-gateway"
    # Many developers share one machine; keep one stack from starving the rest.
    deploy:
      resources:
        limits:
          cpus: "4.0"
          memory: 8G

  client:
    build:
      target: dev
    volumes:
      - ../client:/app/client
      - client_node_modules:/app/client/node_modules

  fileserver:
    environment:
      CLIENT_UPSTREAM_PORT: "5173"

  database:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G
```

- [ ] **Step 2: Create `deploy/compose.local-db.yaml`**

```yaml
# Bundled-database layer. One job: make the server wait for MySQL.
#
# It is a layer of its own rather than part of the dev override because the
# client install runs the bundled database WITHOUT the dev layer — parking
# this dependency in the override would leave ./install.sh racing MySQL on
# first boot, which is exactly the crash-loop it prevents.
#
# It is not in the base either: an always-on server declaring depends_on a
# profile-gated database makes compose refuse to start once the profile is
# turned off for an external database.
#
# Use this layer together with 'local-db' in COMPOSE_PROFILES; `make doctor`
# checks that the two agree.

services:
  server:
    depends_on:
      database:
        condition: service_healthy
```

- [ ] **Step 3: Create `deploy/compose.prod.yaml`**

```yaml
# Production / deployment layer: concerns not already covered by the base.
#
# It makes NO assumption about where the database lives. That is expressed by
# the local-db profile plus EYENED_DATABASE_HOST, which is what lets this one
# layer serve both a client's self-contained install and a site pointed at a
# managed database.

services:

  server:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "8.0"
          memory: 16G

  client:
    restart: unless-stopped

  fileserver:
    restart: unless-stopped

  redis:
    restart: unless-stopped

  database:
    restart: unless-stopped
```

- [ ] **Step 4: Create `deploy/compose.host-ports.yaml`**

```yaml
# Optional: publish the backing services on the host, for DBeaver or a
# host-side alembic. Off by default because a published 3306/6379 is the
# commonest collision between developers sharing a machine.
#
# Enable by appending :compose.host-ports.yaml to COMPOSE_FILE in deploy/.env
# and picking ports nobody else is using.

services:
  database:
    ports:
      - "${DB_PUBLISH_PORT:-13306}:3306"
  redis:
    ports:
      - "${REDIS_PUBLISH_PORT:-16379}:6379"
```

- [ ] **Step 5: Verify each of the three modes resolves the layers it should**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation/deploy

echo "--- developer stack ---"
COMPOSE_FILE=compose.yaml:compose.override.yaml:compose.local-db.yaml:compose.storage.yaml \
  docker-compose config | grep -E 'target:|command:|reload|/app/server|CLIENT_UPSTREAM_PORT|condition:'

echo "--- client install ---"
COMPOSE_FILE=compose.yaml:compose.local-db.yaml:compose.storage.yaml:compose.prod.yaml \
  docker-compose config | grep -E 'target:|command:|reload|/app/server|CLIENT_UPSTREAM_PORT|condition:|restart:'

echo "--- site deploy (make prod) ---"
COMPOSE_PROFILES= docker-compose -f compose.yaml -f compose.storage.yaml -f compose.prod.yaml config --services
```

Expected:
- **developer**: `target: dev`, a `uvicorn ... --reload` command, `../server:/app/server` bind mount, `CLIENT_UPSTREAM_PORT: "5173"`, and `condition: service_healthy` for `database`.
- **client**: `target: prod`, **no** `command:` override, **no** `--reload`, **no** `/app/server` bind mount, `CLIENT_UPSTREAM_PORT: "4173"`, `restart: unless-stopped`, and `condition: service_healthy` for `database`.
- **site**: `client fileserver redis server` — no `database`, no dev override.

- [ ] **Step 6: Verify the failure mode the doctor check exists for**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation/deploy
COMPOSE_PROFILES= COMPOSE_FILE=compose.yaml:compose.local-db.yaml docker-compose config >/dev/null; echo "exit=$?"
```

Expected: a **non-zero** exit with a message about `server` depending on the undefined/disabled service `database`. This is the "layer without profile" half of the invariant Task 9 checks — record the exact wording, because `doctor` must explain it before a user ever sees it.

- [ ] **Step 7: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add deploy/compose.override.yaml deploy/compose.local-db.yaml \
        deploy/compose.prod.yaml deploy/compose.host-ports.yaml
git commit -m "feat(deploy): dev, local-db, prod and host-ports layers

The server->database health dependency gets its own layer so the client
install (bundled DB, no dev override) does not race MySQL on first boot."
```

---

### Task 9: `doctor.sh` — preflight that names the fix

Runs before anything is built, so a failing check costs seconds instead of a full image build. It is the first thing both entry points do.

**Files:**
- Create: `deploy/scripts/doctor.sh`

**Interfaces:**
- Consumes: `lib.sh` (`resolve_compose`, `compose`, `env_get`, `die`, `DEPLOY_DIR`).
- Produces: `doctor.sh [dev|client]`, exit 0 when every check passes, 1 otherwise. Called by `install.sh` (Task 11) as `doctor.sh client`, by `up.sh` as `doctor.sh dev`, and by `make doctor`.

Checks: Docker daemon reachable; compose ≥ 2.15 (the floor this design depends on, asserted everywhere and until now checked nowhere); `HTTP_PORT` free — unless this stack's own fileserver already holds it, since re-runs must work; free disk; a signing key that is actually set; `local-db` profile agrees with the `compose.local-db.yaml` layer; and the `.env` on disk belongs to the entry point being invoked.

- [ ] **Step 1: Create `deploy/scripts/doctor.sh`**

```sh
#!/bin/sh
# Preflight for both entry points. Runs before anything is built, so a failure
# costs seconds rather than an image build. Every failure names the fix.
#
# Usage: doctor.sh [dev|client]
set -eu

MODE=${1:-dev}
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"

case "$MODE" in
    dev|client) ;;
    *) die "usage: doctor.sh [dev|client]" ;;
esac

failed=0
ok()      { printf 'ok    %s\n' "$1"; }
problem() { printf 'FAIL  %s\n' "$1" >&2; failed=1; }

# --- Docker daemon ---------------------------------------------------------
if docker info >/dev/null 2>&1; then
    ok "docker daemon is reachable"
else
    problem "Docker is not running, or is not installed.
      Fix: start Docker Desktop, or install Docker — https://docs.docker.com/get-docker/"
fi

# --- Compose binary and version floor --------------------------------------
resolve_compose
version=$($COMPOSE_BIN version --short 2>/dev/null | tr -d 'v ')
major=${version%%.*}
rest=${version#*.}
minor=${rest%%.*}
case "$major$minor" in
    ''|*[!0-9]*) problem "Could not read a compose version from '$COMPOSE_BIN version --short'.
      Fix: check that Docker Compose is installed correctly." ;;
    *) if [ "$major" -gt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -ge 15 ]; }; then
           ok "compose $version via '$COMPOSE_BIN' (>= 2.15)"
       else
           problem "Docker Compose $version is older than the required 2.15.
      This stack needs profiles, service_healthy conditions and
      deploy.resources outside swarm, none of which work below 2.15.
      Fix: upgrade Docker, or install the compose plugin —
      https://docs.docker.com/compose/install/"
       fi ;;
esac

# --- Layer/profile agreement, and whose .env this is -----------------------
if [ -f "$DEPLOY_DIR/.env" ]; then
    compose_file=$(env_get COMPOSE_FILE)
    profiles=$(env_get COMPOSE_PROFILES)

    case "$profiles"     in *local-db*)              has_profile=yes ;; *) has_profile=no ;; esac
    case "$compose_file" in *compose.local-db.yaml*) has_layer=yes   ;; *) has_layer=no   ;; esac

    if [ "$has_profile" = "$has_layer" ]; then
        ok "the local-db profile and layer agree (both $has_profile)"
    elif [ "$has_profile" = yes ]; then
        problem "COMPOSE_PROFILES contains 'local-db' but COMPOSE_FILE does not list
      compose.local-db.yaml, so the server would start without waiting for
      MySQL and crash-loop on first boot.
      Fix: add :compose.local-db.yaml to COMPOSE_FILE in deploy/.env
           (or drop local-db from COMPOSE_PROFILES to use an external database)."
    else
        problem "COMPOSE_FILE lists compose.local-db.yaml but COMPOSE_PROFILES has no
      'local-db', so 'database' is disabled while 'server' depends on it and
      compose will refuse to start.
      Fix: add local-db to COMPOSE_PROFILES in deploy/.env
           (or remove compose.local-db.yaml from COMPOSE_FILE)."
    fi

    case "$compose_file" in *compose.override.yaml*) has_dev=yes ;; *) has_dev=no ;; esac
    if [ "$MODE" = client ] && [ "$has_dev" = yes ]; then
        problem "deploy/.env was written by 'make up' (it names the dev layer), but you
      are running ./install.sh, which builds the production stack. Continuing
      would quietly build the other stack.
      Fix: run 'make up' instead, or remove deploy/.env to start over.
           (Removing .env keeps your data; 'make reset' is what deletes it.)"
    elif [ "$MODE" = dev ] && [ "$has_dev" = no ]; then
        problem "deploy/.env was written by ./install.sh (it has no dev layer), but you
      are running 'make up', which expects the developer stack.
      Fix: run ./install.sh instead, or remove deploy/.env to start over.
           (Removing .env keeps your data; 'make reset' is what deletes it.)"
    else
        ok "deploy/.env matches the '$MODE' entry point"
    fi

    if [ -n "$(env_get EYENED_API_SECRET_KEY)" ]; then
        ok "EYENED_API_SECRET_KEY is set"
    else
        problem "EYENED_API_SECRET_KEY is empty in deploy/.env, so sessions cannot be
      signed. It is normally generated on first run.
      Fix: remove deploy/.env and re-run, or set it to a long random value."
    fi
else
    ok "no deploy/.env yet — it will be created from .env.example"
fi

# --- HTTP_PORT ------------------------------------------------------------
http_port=$(env_get HTTP_PORT)
[ -n "$http_port" ] || http_port=$(env_get HTTP_PORT "$DEPLOY_DIR/.env.example")

port_probe() {
    # 0 = in use, 1 = free, 2 = cannot tell. Neither nc nor python3 is
    # guaranteed on a stock macOS or WSL host, so "cannot tell" is a real case
    # and must not be reported as "free".
    if command -v nc >/dev/null 2>&1; then
        nc -z 127.0.0.1 "$1" >/dev/null 2>&1 && return 0 || return 1
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import socket, sys
s = socket.socket(); s.settimeout(1)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)' "$1" && return 0 || return 1
    fi
    return 2
}

# A re-run must not trip over its own listener.
ours=$(compose ps -q fileserver 2>/dev/null || true)
if [ -n "$ours" ]; then
    ok "port $http_port is held by this stack's own fileserver (this is a re-run)"
else
    set +e
    port_probe "$http_port"
    probe=$?
    set -e
    case "$probe" in
        0) problem "Port $http_port is already in use, so the platform cannot bind it.
      Fix: set HTTP_PORT in deploy/.env to a free port (on a machine shared
           with other developers, pick one nobody else is using), or stop
           whatever is holding $http_port." ;;
        2) ok "port $http_port: no probe tool (nc/python3) here, check skipped" ;;
        *) ok "port $http_port is free" ;;
    esac
fi

# --- Disk ------------------------------------------------------------------
avail_kb=$(df -Pk "$DEPLOY_DIR" | awk 'NR == 2 {print $4}')
if [ "${avail_kb:-0}" -ge 10485760 ]; then
    ok "$((avail_kb / 1048576)) GiB free on this filesystem"
else
    problem "Only $((avail_kb / 1024)) MiB free where Docker will build. Images plus the
      database volume need roughly 10 GiB.
      Fix: free space, or move Docker's data root to a larger filesystem."
fi

if [ "$failed" -ne 0 ]; then
    echo >&2
    die "preflight failed — nothing was built. Fix the items above and re-run."
fi
echo "preflight passed."
```

- [ ] **Step 2: Verify a clean pass**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
chmod +x deploy/scripts/doctor.sh
rm -f deploy/.env
deploy/scripts/doctor.sh dev; echo "exit=$?"
```

Expected: every line starts `ok`, ends `preflight passed.`, `exit=0`.

- [ ] **Step 3: Verify each failure names its fix**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
cp deploy/.env.example deploy/.env

# (a) profile without layer
sed 's|^COMPOSE_FILE=.*|COMPOSE_FILE=compose.yaml:compose.override.yaml:compose.storage.yaml|' \
    deploy/.env > deploy/.env.t && mv deploy/.env.t deploy/.env
deploy/scripts/doctor.sh dev; echo "exit=$?"

# (b) layer without profile
cp deploy/.env.example deploy/.env
sed 's|^COMPOSE_PROFILES=.*|COMPOSE_PROFILES=|' deploy/.env > deploy/.env.t && mv deploy/.env.t deploy/.env
deploy/scripts/doctor.sh dev; echo "exit=$?"

# (c) wrong entry point for this .env
cp deploy/.env.example deploy/.env
deploy/scripts/doctor.sh client; echo "exit=$?"

# (d) occupied HTTP_PORT
cp deploy/.env.example deploy/.env
port=$(sed -n 's/^HTTP_PORT=//p' deploy/.env)
docker run -d --rm --name port-probe -p "$port:80" nginx:1.27-alpine >/dev/null
deploy/scripts/doctor.sh dev; echo "exit=$?"
docker stop port-probe >/dev/null
rm -f deploy/.env
```

Expected: (a) names `compose.local-db.yaml` and says to add it to `COMPOSE_FILE`; (b) explains the disabled-service error and says to add `local-db` to `COMPOSE_PROFILES`; (c) says `.env` was written by `make up` while `./install.sh` was invoked; (d) names the port and says to change `HTTP_PORT`. All four exit `1`.

- [ ] **Step 4: Syntax check and commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
docker run --rm -v "$PWD:/w" -w /w alpine sh -n deploy/scripts/doctor.sh && echo "sh: syntax ok"
git add deploy/scripts/doctor.sh
git commit -m "feat(deploy): preflight that checks the compose floor, ports, disk and layer/profile agreement"
```

---

### Task 10: `bootstrap.sh` — first run, gated on database state

Runs from `./install.sh` and `make up` alike — the two entry points where this stack owns its database — and never from `make prod`. Idempotent.

Gating on **state** rather than on which stack is running is what gives the client install a bootstrap at all; tying it to the dev path would leave the install that most needs it with none.

**Files:**
- Create: `deploy/scripts/bootstrap.sh`

**Interfaces:**
- Consumes: Task 1's state-based confirmation gate (`eorm initialize-database` must complete non-interactively on an empty database); `lib.sh`; a running stack with a healthy `database` and a `server` container.
- Produces: `bootstrap.sh`, safe to re-run. Called last by `install.sh` and `up.sh`.

- [ ] **Step 1: Create `deploy/scripts/bootstrap.sh`**

```sh
#!/bin/sh
# First-run bootstrap: create the schema, seed form schemas, create an admin.
#
# Gated on database STATE, not on which stack is running: it acts only when
# this stack OWNS its database (local-db profile) and that database is EMPTY.
# It never migrates an existing database — the same .env can point at shared
# or production data, so drift is reported and left alone.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

ALEMBIC="alembic -c orm/migrations/alembic.ini"

# --- 1. Does this stack own its database? ---------------------------------
case "$(env_get COMPOSE_PROFILES)" in
    *local-db*) ;;
    *)
        echo "bootstrap: this stack does not run the bundled database (no 'local-db'"
        echo "bootstrap: profile), so it cannot verify or safely initialise the"
        echo "bootstrap: database it points at. Nothing to do."
        exit 0
        ;;
esac

# --- 2. Wait for MySQL to report healthy -----------------------------------
cid=$(compose ps -q database || true)
[ -n "$cid" ] || die "bootstrap: the 'database' service is not running.
      Fix: start the stack first (./install.sh or make up)."

printf 'bootstrap: waiting for MySQL to become healthy'
status=unknown
i=0
while [ "$i" -lt 120 ]; do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo unknown)
    [ "$status" = healthy ] && break
    printf '.'
    sleep 2
    i=$((i + 1))
done
echo
[ "$status" = healthy ] || die "bootstrap: MySQL did not become healthy within 240s (last status: $status).
      Look at: $COMPOSE_BIN logs database"

# --- 3. Empty or populated? ------------------------------------------------
tables=$(compose exec -T server python -c '
from sqlalchemy import inspect
from eyened_orm import Database
print(len(inspect(Database().engine).get_table_names()))
' | tr -d '\r' | tail -n 1)

if [ "$tables" = "0" ]; then
    echo "bootstrap: the database is empty — creating the schema and seeding form schemas."
    # The supported fresh-install path: create_all + stamp alembic at head, so
    # later upgrades apply only new migrations. NOT `alembic upgrade head`:
    # replaying the whole chain from zero is not a path this repo maintains.
    compose exec -T server eorm initialize-database --seed-form-schemas
else
    echo "bootstrap: the database already has $tables tables — it will not be migrated."
    current=$(compose exec -T server $ALEMBIC current 2>/dev/null | tr -d '\r' | grep -v '^$' | tail -n 1)
    head=$(compose exec -T server $ALEMBIC heads 2>/dev/null | tr -d '\r' | grep -v '^$' | tail -n 1)
    if [ "${current%% *}" = "${head%% *}" ]; then
        echo "bootstrap: schema is at head ($head). Nothing to do."
    else
        echo "bootstrap: WARNING — this database is not at the latest revision."
        echo "bootstrap:   current: ${current:-<none>}"
        echo "bootstrap:   head:    ${head:-<unknown>}"
        echo "bootstrap: Run 'make migrate' when you are sure this is the database"
        echo "bootstrap: you want to migrate. Nothing was changed."
    fi
fi

# --- 4. An admin account, once ---------------------------------------------
accounts=$(compose exec -T server python -c '
from sqlalchemy import func, select
from eyened_orm import Creator, Database
with Database().get_session() as session:
    print(session.execute(select(func.count()).select_from(Creator)).scalar_one())
' | tr -d '\r' | tail -n 1)

if [ "$accounts" = "0" ]; then
    admin_password=$(gen_password)
    compose exec -T server eorm create-user \
        --username admin \
        --password "$admin_password" \
        --description "created by deploy/scripts/bootstrap.sh on first run"
    cat <<EOF

------------------------------------------------------------------------
An administrator account was created. This password is shown ONCE:

    username: admin
    password: $admin_password

Copy it now. More users can be created from the user interface.
------------------------------------------------------------------------
EOF
else
    echo "bootstrap: $accounts account(s) already exist — not creating an admin."
fi
```

- [ ] **Step 2: Bring up a stack to bootstrap against**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
chmod +x deploy/scripts/bootstrap.sh
cp deploy/.env.example deploy/.env
sed 's|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=eyened-bootstrap-probe|' deploy/.env > deploy/.env.t
mv deploy/.env.t deploy/.env
sed 's|^HTTP_PORT=.*|HTTP_PORT=18080|' deploy/.env > deploy/.env.t && mv deploy/.env.t deploy/.env
sed 's|^ADMINER_PORT=.*|ADMINER_PORT=18081|' deploy/.env > deploy/.env.t && mv deploy/.env.t deploy/.env
sh -c 'REPO_ROOT=$PWD; . deploy/scripts/lib.sh; env_set EYENED_API_SECRET_KEY "$(gen_secret)"; env_set EYENED_REDIS_PASSWORD "$(gen_secret)"'
deploy/scripts/gen-storage.sh
(cd deploy && docker-compose up -d --build)
```

Expected: all services start; `docker-compose ps` shows `database` healthy.

- [ ] **Step 3: Bootstrap an empty database**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
deploy/scripts/bootstrap.sh
```

Expected: `the database is empty — creating the schema...`; `eorm initialize-database` prints `Target database ... has no tables — proceeding without confirmation` (Task 1's change, doing its job) followed by table creation, alembic stamping, and seeded form schemas; then an admin password block.

- [ ] **Step 4: Verify idempotence**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
deploy/scripts/bootstrap.sh
```

Expected: `the database already has N tables — it will not be migrated`, `schema is at head (...)`, `1 account(s) already exist — not creating an admin`. No error, no duplicate admin, no migration.

- [ ] **Step 5: Verify it declines to touch a database it does not own**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
sh -c 'REPO_ROOT=$PWD; . deploy/scripts/lib.sh; env_set COMPOSE_PROFILES ""'
deploy/scripts/bootstrap.sh; echo "exit=$?"
sh -c 'REPO_ROOT=$PWD; . deploy/scripts/lib.sh; env_set COMPOSE_PROFILES "local-db"'
```

Expected: `this stack does not run the bundled database ... Nothing to do.` and `exit=0`.

- [ ] **Step 6: Tear the probe stack down, syntax check, commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
(cd deploy && docker-compose down -v)
rm -f deploy/.env
docker run --rm -v "$PWD:/w" -w /w alpine sh -n deploy/scripts/bootstrap.sh && echo "sh: syntax ok"
git add deploy/scripts/bootstrap.sh
git commit -m "feat(deploy): idempotent first-run bootstrap gated on database state

Creates schema, seeds form schemas and an admin only when this stack owns
its database and that database is empty; reports drift instead of
migrating, and declines external databases outright."
```

---

### Task 11: The two entry points — `install.sh`, `up.sh`, and the Makefile

`install.sh` is the published door because Docker is its only prerequisite: `make` does not exist on Windows, arrives on macOS only with the Xcode Command Line Tools, and is a separate package on minimal Linux images. The Makefile is developer ergonomics over the same scripts.

**Files:**
- Create: `install.sh` (root), `deploy/scripts/up.sh`
- Modify: `Makefile` (root) — keep the existing `gen-openapi` / `gen-types` targets

**Interfaces:**
- Consumes: `lib.sh` (`first_run_env`, `compose`, `print_day2`, `resolve_compose`), `doctor.sh`, `gen-storage.sh`, `bootstrap.sh`, `compose-bin.sh`.
- Produces: `./install.sh` (client), `make up` → `deploy/scripts/up.sh` (developer), `make install` → `./install.sh` (alias), plus `down`, `logs`, `doctor`, `prod`.

- [ ] **Step 1: Create root `install.sh`**

```sh
#!/bin/sh
# The client entry point for the Eyened platform.
#
# Docker is the only prerequisite: this is a script and not a make target
# precisely so that no build tool is needed. It installs the PRODUCTION stack
# (gunicorn, built client, no source mounts) on a database this stack owns.
#
#   git clone --branch <tag> https://github.com/Eyened/eyened-platform.git
#   cd eyened-platform
#   ./install.sh
#
# Re-running it on an installed stack is safe: it rebuilds and re-bootstraps.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")" && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"

echo "==> checking this machine"
"$DEPLOY_DIR/scripts/doctor.sh" client

resolve_compose
first_run_env client
"$DEPLOY_DIR/scripts/gen-storage.sh"

echo "==> building images and starting the platform"
echo "    (the first run builds everything from source and takes a while)"
compose up -d --build

"$DEPLOY_DIR/scripts/bootstrap.sh"
print_day2
```

- [ ] **Step 2: Create `deploy/scripts/up.sh`**

```sh
#!/bin/sh
# The developer entry point: the same machinery as ./install.sh, with the dev
# layer instead of the prod one — uvicorn --reload over bind-mounted sources
# and a vite dev server with hot reload.
#
# Reached as `make up`.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"

echo "==> checking this machine"
"$DEPLOY_DIR/scripts/doctor.sh" dev

resolve_compose
first_run_env dev
"$DEPLOY_DIR/scripts/gen-storage.sh"

echo "==> building images and starting the developer stack"
compose up -d --build

"$DEPLOY_DIR/scripts/bootstrap.sh"
print_day2
```

- [ ] **Step 3: Rewrite the root `Makefile`**

```make
# Thin aliases for developers. Every target's logic lives in deploy/scripts/
# or install.sh, so that nothing on the client path needs make: `make` is
# absent on Windows, ships with the Xcode Command Line Tools on macOS, and is
# a separate package on minimal Linux images.
#
# See deploy/README.md for what each of these does.

SHELL := /bin/sh
REPO_ROOT := $(shell git rev-parse --show-toplevel)
DEPLOY := $(REPO_ROOT)/deploy
COMPOSE := $(shell $(REPO_ROOT)/deploy/scripts/compose-bin.sh)

PY := python3
OPENAPI_DIR := $(REPO_ROOT)/client/src/types
OPENAPI_JSON := $(OPENAPI_DIR)/openapi.json
OPENAPI_TS := $(REPO_ROOT)/client/src/types/openapi.ts

.PHONY: install doctor up down logs prod migrate db-shell \
        gen-openapi gen-types gen-client-types

## install: the client install (production stack, bundled database). Alias for ./install.sh.
install:
	$(REPO_ROOT)/install.sh

## doctor: preflight checks without building anything.
doctor:
	$(DEPLOY)/scripts/doctor.sh dev

## up: the developer stack — hot reload, source mounted, bundled database.
up:
	$(DEPLOY)/scripts/up.sh

## down: stop this stack.
down:
	cd $(DEPLOY) && $(COMPOSE) down

## logs: follow logs.
logs:
	cd $(DEPLOY) && $(COMPOSE) logs -f

## prod: a site deployment against an EXTERNAL database.
# An explicit -f list overrides COMPOSE_FILE from .env entirely, so the
# generated storage layer must be named here too — prod serves images through
# the same mounts dev does. This differs from ./install.sh in exactly one
# layer: no compose.local-db.yaml, because the database is someone else's.
prod:
	cd $(DEPLOY) && $(COMPOSE) -f compose.yaml -f compose.storage.yaml -f compose.prod.yaml up -d --build

## migrate: apply pending migrations inside the server container.
# Interactive on purpose: alembic's own confirmation prompt still guards
# manual runs against a populated database.
migrate:
	cd $(DEPLOY) && $(COMPOSE) exec -it server alembic -c orm/migrations/alembic.ini upgrade head

## db-shell: a MySQL shell in the bundled database.
db-shell:
	cd $(DEPLOY) && $(COMPOSE) exec -it database sh -c 'exec mysql -u"$$MYSQL_USER" -p"$$MYSQL_PASSWORD" "$$MYSQL_DATABASE"'

gen-openapi:
	$(PY) $(REPO_ROOT)/dev/generate_openapi.py $(OPENAPI_DIR)

gen-types: gen-openapi
	npx --yes openapi-typescript@7 $(OPENAPI_JSON) -o $(OPENAPI_TS)

gen-client-types: gen-types
	@echo "Types generated at $(OPENAPI_TS)"
```

- [ ] **Step 4: Make the entry points executable, syntax-check, and commit**

Commit before the clean-clone checks: a clone only carries committed state, so this is what makes the next three steps test the real thing rather than a working tree.

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
chmod +x install.sh deploy/scripts/up.sh
docker run --rm -v "$PWD:/w" -w /w alpine sh -n install.sh deploy/scripts/up.sh && echo "sh: syntax ok"
make -n up down logs doctor prod migrate >/dev/null && echo "make: all targets resolve"
git add install.sh deploy/scripts/up.sh Makefile
git commit -m "feat(deploy): ./install.sh as the client entry point, make targets for developers

The install records its layer list in deploy/.env, so day-2 commands are
plain docker-compose from deploy/ with no -f flags and no make."
```

- [ ] **Step 5: Run the client install from a genuinely clean clone**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
rm -rf /tmp/eyened-clean-client
git clone --no-hardlinks --branch feature/deploy-consolidation . /tmp/eyened-clean-client
cd /tmp/eyened-clean-client
sed -i 's/^HTTP_PORT=.*/HTTP_PORT=18080/;s/^ADMINER_PORT=.*/ADMINER_PORT=18081/;s/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=eyened-clean-client/' deploy/.env.example
./install.sh
```

Expected: preflight passes; images build; MySQL comes up healthy before the server; bootstrap creates the schema and prints a one-time admin password; the banner prints the URL and three `docker-compose` day-2 commands.

- [ ] **Step 6: Prove it really is the production stack**

```bash
cd /tmp/eyened-clean-client/deploy
docker-compose exec -T server sh -c 'ps ax | grep -c "[g]unicorn"'
docker-compose exec -T server sh -c 'ps ax | grep -c "[u]vicorn --reload"' || echo "0 uvicorn --reload (expected)"
docker inspect "$(docker-compose ps -q server)" --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
curl -sf http://localhost:18080/api/health && echo " <- api healthy"
curl -sI http://localhost:18080/ | head -1
```

Expected: at least one gunicorn process; no `uvicorn --reload`; the only server mount is platform storage (**no** `../server` or `../client` bind mount); the API answers; `/` returns `200`.

- [ ] **Step 7: Prove Docker is the only prerequisite**

The regression test for the entry point being a script. Do **not** try to remove `make` by filtering its directory out of `PATH` — `make` lives in `/usr/bin` alongside `docker` and everything else, so that would test nothing except a broken environment. Build a `PATH` that contains exactly the tools the client path is allowed to assume:

```bash
cd /tmp/eyened-clean-client
(cd deploy && docker-compose down)

mkdir -p /tmp/nomake/bin
for tool in docker docker-compose git sh sed grep awk tr cat mktemp df nc openssl python3 curl; do
    p=$(command -v "$tool" 2>/dev/null) && ln -sf "$p" /tmp/nomake/bin/ || true
done

env PATH=/tmp/nomake/bin sh -c '
  command -v make >/dev/null && { echo "make is still reachable — fix the probe"; exit 1; }
  ./install.sh
'

# ...and the day-2 commands it printed, the same way
env PATH=/tmp/nomake/bin sh -c 'cd deploy && docker-compose logs --tail 5 server'
env PATH=/tmp/nomake/bin sh -c 'cd deploy && docker-compose down'
env PATH=/tmp/nomake/bin sh -c 'cd deploy && docker-compose up -d'
rm -rf /tmp/nomake
```

Expected: the install completes with `make` unreachable, and all three day-2 commands succeed. `logs` shows the gunicorn server, not a dev container. Nothing on the client path may reach for a build tool, and nothing may require an `-f` list the operator has to assemble.

- [ ] **Step 8: Run the developer stack from a second clean clone**

```bash
rm -rf /tmp/eyened-clean-dev
git clone --no-hardlinks --branch feature/deploy-consolidation \
    /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation /tmp/eyened-clean-dev
cd /tmp/eyened-clean-dev
sed -i 's/^HTTP_PORT=.*/HTTP_PORT=18090/;s/^ADMINER_PORT=.*/ADMINER_PORT=18091/;s/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=eyened-clean-dev/' deploy/.env.example
make up
(cd deploy && docker-compose exec -T server sh -c 'ps ax | grep -c "[u]vicorn"')
docker-compose ls | grep -c eyened-clean
```

Expected: `make up` succeeds, the server runs `uvicorn --reload`, and both stacks coexist — `docker-compose ls` shows two projects with different names, ports, and volumes, and neither publishes a database port. This is the multi-developer isolation requirement that the gitignored personal compose file used to serve.

Then confirm hot reload actually works:

```bash
cd /tmp/eyened-clean-dev
printf '\n# hot-reload probe\n' >> server/main.py
sleep 5
(cd deploy && docker-compose logs --tail 20 server | grep -i reload)
git checkout server/main.py
```

Expected: the log shows uvicorn detecting the change and reloading, with no rebuild.

- [ ] **Step 9: Clean up the probe stacks**

```bash
(cd /tmp/eyened-clean-client/deploy && docker-compose down -v) || true
(cd /tmp/eyened-clean-dev/deploy && docker-compose down -v) || true
rm -rf /tmp/eyened-clean-client /tmp/eyened-clean-dev
```

If any of steps 5–8 turned up a defect, fix it and amend the Step 4 commit rather than committing a broken entry point followed by a repair.

---

### Task 12: Operations — reset, snapshots, dumps, storage check

The rest of the Makefile surface, and the two `database/` scripts moved across. The snapshot pair matters because MySQL auto-commits DDL per statement, so a half-applied migration cannot be reliably undone with `alembic downgrade` — it generalizes a procedure currently hand-written with one developer's container name baked in.

**Files:**
- Create: `deploy/scripts/reset.sh`, `deploy/scripts/check-storage.sh`, `deploy/scripts/db-snapshot.sh`, `deploy/scripts/db-restore.sh`
- Move: `database/load_dump.sh` → `deploy/scripts/load_dump.sh`, `database/save_dump.sh` → `deploy/scripts/save_dump.sh`
- Modify: `deploy/compose.yaml` (add the `xtrabackup` service under a `backup` profile), `Makefile`

**Interfaces:**
- Consumes: `lib.sh`; `COMPOSE_PROJECT_NAME` (volume names derive from it).
- Produces: `make reset`, `make check-storage`, `make db-snapshot NAME=…`, `make db-restore NAME=…`; the dump scripts run from `deploy/`.

- [ ] **Step 1: Add the backup service to `deploy/compose.yaml`**

Insert after the `adminer` service:

```yaml
  # Used only by deploy/scripts/{load,save}_dump.sh.
  xtrabackup:
    profiles: ["backup"]
    image: percona/percona-xtrabackup:8.0
    volumes:
      - db_data:/var/lib/mysql
```

- [ ] **Step 2: Create `deploy/scripts/reset.sh`**

```sh
#!/bin/sh
# Stop the stack and DELETE its volumes — database and platform storage.
#
# Refuses outright when this stack is attached to storage or a database it
# does not own, so it cannot be aimed at shared or production data.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

platform_storage=$(env_get PLATFORM_STORAGE_PATH)
[ -z "$platform_storage" ] || die "refusing: PLATFORM_STORAGE_PATH is set to $platform_storage.
      This stack is attached to storage it does not own. Unset it in
      deploy/.env if you really mean to reset a stack with its own volume."

case "$(env_get COMPOSE_PROFILES)" in
    *local-db*) ;;
    *) die "refusing: this stack uses an external database (no 'local-db' profile).
      Reset only removes volumes this stack owns; the external database would
      be untouched, which is not what 'reset' implies." ;;
esac

db_host=$(env_get EYENED_DATABASE_HOST)
case "${db_host:-database}" in
    database) ;;
    *) die "refusing: EYENED_DATABASE_HOST is '$db_host', not the bundled 'database'.
      Point it back at the bundled database, or use the tools of whatever
      server it names." ;;
esac

project=$(env_get COMPOSE_PROJECT_NAME)
cat <<EOF
This will stop the '$project' stack and permanently delete its volumes:

  ${project}_db_data           the entire database
  ${project}_platform_storage  thumbnails and segmentations.zarr

EOF
printf "Type the project name (%s) to confirm: " "$project"
read -r answer
[ "$answer" = "$project" ] || die "cancelled — nothing was removed."

compose down -v
echo "removed. Run ./install.sh or make up to start over."
```

- [ ] **Step 3: Create `deploy/scripts/check-storage.sh`**

```sh
#!/bin/sh
# Report disagreement between configured mounts and StorageBackend rows.
#
# Deliberately NOT part of ./install.sh or make up: generation has to work
# before any database exists, which is exactly the state a first run is in.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

compose exec -T server python -c '
import json, os
from sqlalchemy import select
from eyened_orm import Database, StorageBackend

configured = set(json.loads(os.environ.get("EYENED_STORAGE_MOUNTS") or "{}"))
with Database().get_session() as session:
    rows = set(session.execute(select(StorageBackend.Key)).scalars())

for key in sorted(configured - rows):
    print(f"configured but no StorageBackend row: {key}")
for key in sorted(rows - configured):
    print(f"StorageBackend row but not configured: {key}")
if configured == rows:
    print(f"storage-mounts.json and StorageBackend rows agree ({len(rows)} key(s)).")
'
```

- [ ] **Step 4: Create the snapshot pair**

`deploy/scripts/db-snapshot.sh`:

```sh
#!/bin/sh
# Cold snapshot of the bundled MySQL data volume.
#
# Cold, not hot, on purpose: MySQL auto-commits DDL per statement, so a
# half-applied migration cannot be reliably undone with `alembic downgrade`.
# This is the safety net for `make migrate`.
#
# Usage: db-snapshot.sh <name>
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

name=${1:-}
[ -n "$name" ] || die "usage: make db-snapshot NAME=<name>"

project=$(env_get COMPOSE_PROJECT_NAME)
volume="${project}_db_data"
out="$DEPLOY_DIR/snapshots"
mkdir -p "$out"

echo "==> stopping the database"
compose stop database

echo "==> writing $out/$name.tgz from volume $volume"
docker run --rm \
    -v "$volume:/data:ro" \
    -v "$out:/out" \
    alpine tar czf "/out/$name.tgz" -C /data .

echo "==> starting the database"
compose start database
echo "snapshot written: $out/$name.tgz"
```

`deploy/scripts/db-restore.sh`:

```sh
#!/bin/sh
# Restore a snapshot written by db-snapshot.sh, replacing the data volume.
#
# Usage: db-restore.sh <name>
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

name=${1:-}
[ -n "$name" ] || die "usage: make db-restore NAME=<name>"

project=$(env_get COMPOSE_PROJECT_NAME)
volume="${project}_db_data"
archive="$DEPLOY_DIR/snapshots/$name.tgz"
[ -f "$archive" ] || die "error: no snapshot at $archive"

printf "Replace the contents of volume %s from %s? [y/N] " "$volume" "$name.tgz"
read -r answer
case "$answer" in y|Y|yes|YES) ;; *) die "cancelled." ;; esac

echo "==> stopping the database"
compose stop database

docker run --rm \
    -v "$volume:/data" \
    -v "$DEPLOY_DIR/snapshots:/in:ro" \
    alpine sh -c "rm -rf /data/* /data/..?* 2>/dev/null; tar xzf /in/$name.tgz -C /data"

echo "==> starting the database"
compose start database
echo "restored from $archive"
```

- [ ] **Step 5: Move the dump scripts and fix their paths**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git mv database/load_dump.sh deploy/scripts/load_dump.sh
git mv database/save_dump.sh deploy/scripts/save_dump.sh
```

In both files, change the directory resolution so compose runs from `deploy/` rather than from the script's own directory, and update the usage text. In `load_dump.sh` and `save_dump.sh` replace:

```bash
DIR="$(cd "$(dirname "$0")" && pwd)"
```

with:

```bash
# Compose (and .env) live in deploy/, one level up from scripts/.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
```

and in each `compose()` function replace the body's bare invocations so they run in `deploy/`:

```bash
compose() {
  if docker compose version >/dev/null 2>&1; then
    ( cd "$DIR" && docker compose "$@" )
  elif command -v docker-compose >/dev/null 2>&1; then
    ( cd "$DIR" && docker-compose "$@" )
  else
    echo "error: neither 'docker compose' nor 'docker-compose' is available" >&2
    exit 1
  fi
}
```

Update the usage comments at the top of each file: `Intended to be run from database/.` → `Run from anywhere; paths are resolved relative to deploy/.`, and `database/.env` → `deploy/.env`.

- [ ] **Step 6: Add the remaining Makefile targets**

Append to `.PHONY` (`reset check-storage db-snapshot db-restore db-dump-save db-dump-load`) and add:

```make
## reset: stop this stack and delete its volumes. Guarded; asks for confirmation.
reset:
	$(DEPLOY)/scripts/reset.sh

## check-storage: report configured mounts with no StorageBackend row, and vice versa.
check-storage:
	$(DEPLOY)/scripts/check-storage.sh

## db-snapshot NAME=x: cold snapshot of the bundled database volume.
db-snapshot:
	$(DEPLOY)/scripts/db-snapshot.sh $(NAME)

## db-restore NAME=x: restore a snapshot taken by db-snapshot.
db-restore:
	$(DEPLOY)/scripts/db-restore.sh $(NAME)
```

- [ ] **Step 7: Exercise the guards and the snapshot round-trip**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
chmod +x deploy/scripts/reset.sh deploy/scripts/check-storage.sh \
         deploy/scripts/db-snapshot.sh deploy/scripts/db-restore.sh

# Guard 1: shared platform storage
cp deploy/.env.example deploy/.env
printf 'PLATFORM_STORAGE_PATH=/mnt/oogergo/eyened/eyened_platform\n' >> deploy/.env
deploy/scripts/reset.sh; echo "exit=$?"

# Guard 2: external database
cp deploy/.env.example deploy/.env
sh -c 'REPO_ROOT=$PWD; . deploy/scripts/lib.sh; env_set COMPOSE_PROFILES ""'
deploy/scripts/reset.sh; echo "exit=$?"
rm -f deploy/.env
```

Expected: both refuse with a message naming the setting, `exit=1`, and nothing is removed.

Then, against a running stack (bring one up as in Task 10 Step 2):

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
deploy/scripts/db-snapshot.sh before-migration
(cd deploy && docker-compose exec -T server alembic -c orm/migrations/alembic.ini current)
deploy/scripts/db-restore.sh before-migration   # answer y
(cd deploy && docker-compose exec -T server alembic -c orm/migrations/alembic.ini current)
deploy/scripts/check-storage.sh
```

Expected: the snapshot is written under `deploy/snapshots/`; `alembic current` reports the same revision before and after the restore; `check-storage` reports agreement (0 keys, 0 rows on a fresh install).

- [ ] **Step 8: Syntax check, tear down, commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
(cd deploy && docker-compose down -v) || true
rm -f deploy/.env
docker run --rm -v "$PWD:/w" -w /w alpine sh -n \
  deploy/scripts/reset.sh deploy/scripts/check-storage.sh \
  deploy/scripts/db-snapshot.sh deploy/scripts/db-restore.sh && echo "sh: syntax ok"
git add deploy/scripts/ deploy/compose.yaml Makefile
git add -u database/
git commit -m "feat(deploy): reset guards, database snapshots, dump scripts, storage check

Snapshot/restore replaces a hand-written procedure that hardcoded one
developer's container name; reset refuses to run against shared storage
or a database this stack does not own."
```

---

### Task 13: Keycloak under an `oidc` profile

Move the Keycloak override into the base file as a profile-gated service, and rename the three `DEV_*` variables as it moves. These files carry the **only** `${DEV_PUBLIC_HOST}` / `${DEV_NGINX_PORT}` references in the repository.

**Files:**
- Move: `dev/keycloak/entrypoint.sh`, `dev/keycloak/realm-eyened-dev.json.template`, `dev/keycloak/README.md` → `deploy/keycloak/`
- Delete: `dev/keycloak/docker-compose.keycloak.yml` (folded into `compose.yaml`)
- Modify: `deploy/compose.yaml`, `deploy/keycloak/entrypoint.sh`, `deploy/keycloak/README.md`

**Interfaces:**
- Consumes: `PUBLIC_HOST`, `HTTP_PORT`, `KEYCLOAK_PORT`, `KEYCLOAK_ADMIN_PASSWORD` from `deploy/.env`; the server OIDC variables already declared in `compose.yaml` (Task 7).
- Produces: profile `oidc`. Off by default so "clone and run" stays lean.

- [ ] **Step 1: Move the files**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
mkdir -p deploy/keycloak
git mv dev/keycloak/entrypoint.sh deploy/keycloak/entrypoint.sh
git mv dev/keycloak/realm-eyened-dev.json.template deploy/keycloak/realm-eyened-dev.json.template
git mv dev/keycloak/README.md deploy/keycloak/README.md
git rm dev/keycloak/docker-compose.keycloak.yml
```

- [ ] **Step 2: Rename the variables in `deploy/keycloak/entrypoint.sh`**

```bash
#!/bin/bash
set -euo pipefail

REDIRECT_URI="http://${PUBLIC_HOST:?}:${HTTP_PORT:?}/users/oidc-callback"
WEB_ORIGIN="http://${PUBLIC_HOST}:${HTTP_PORT}"

mkdir -p /opt/keycloak/data/import
sed \
  -e "s|__REDIRECT_URI__|${REDIRECT_URI}|g" \
  -e "s|__WEB_ORIGIN__|${WEB_ORIGIN}|g" \
  /opt/keycloak/import-template/realm-eyened-dev.json \
  > /opt/keycloak/data/import/realm-eyened-dev.json

exec /opt/keycloak/bin/kc.sh start-dev --import-realm
```

- [ ] **Step 3: Add the service to `deploy/compose.yaml`**

Insert before `volumes:` at the end of the file:

```yaml
  # Development/testing OIDC provider. Off by default: add 'oidc' to
  # COMPOSE_PROFILES to enable. The realm template is a dev realm — this is
  # not a production identity provider.
  keycloak:
    profiles: ["oidc"]
    image: quay.io/keycloak/keycloak:26.0
    env_file: .env
    entrypoint: ["/bin/bash", "/opt/keycloak/entrypoint.sh"]
    environment:
      KC_HOSTNAME: ${PUBLIC_HOST:-localhost}
      KC_HOSTNAME_PORT: ${KEYCLOAK_PORT:-8180}
      KC_HOSTNAME_STRICT: "false"
      KC_HOSTNAME_STRICT_HTTPS: "false"
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD:-admin}
    ports:
      - "${KEYCLOAK_PORT:-8180}:8080"
    volumes:
      - ./keycloak/entrypoint.sh:/opt/keycloak/entrypoint.sh:ro
      - ./keycloak/realm-eyened-dev.json.template:/opt/keycloak/import-template/realm-eyened-dev.json:ro
```

The server's `EYENED_OIDC_*` variables are already in the base (Task 7) — inert while `EYENED_API_AUTH_OIDC_ENABLED` is false. The `extra_hosts` entry that lets the server reach a host-published Keycloak lives in the **dev override** (Task 8) rather than the base, because mapping a real `PUBLIC_HOST` to `host-gateway` would be wrong in a site deployment.

- [ ] **Step 4: Add the OIDC block to `deploy/.env.example`**

Append:

```bash
# ---- OIDC (optional) -------------------------------------------------------
# Add 'oidc' to COMPOSE_PROFILES above to run the bundled Keycloak, and set
# PUBLIC_HOST to the hostname you use in the browser. See deploy/keycloak/README.md.
# EYENED_API_AUTH_OIDC_ENABLED=true
# EYENED_OIDC_CLIENT_ID=eyened-platform
# EYENED_OIDC_CLIENT_SECRET=eyened-dev-secret   # must match realm-eyened-dev.json.template
# EYENED_OIDC_PROVIDER_NAME=Keycloak
# EYENED_OIDC_CREATE_NEW_ACCOUNTS=true
# KEYCLOAK_PORT=8180
# KEYCLOAK_ADMIN_PASSWORD=admin
```

- [ ] **Step 5: Update `deploy/keycloak/README.md`**

Replace `DEV_PUBLIC_HOST` with `PUBLIC_HOST` and `DEV_NGINX_PORT` with `HTTP_PORT` throughout, and replace the layering instructions (`docker compose -f docker-compose.yml -f keycloak/docker-compose.keycloak.yml up`) with: add `oidc` to `COMPOSE_PROFILES` in `deploy/.env`, then `make up`.

- [ ] **Step 6: Verify the profile and the rename**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
cp deploy/.env.example deploy/.env
(cd deploy && docker-compose config --services | sort)
(cd deploy && COMPOSE_PROFILES=local-db,oidc docker-compose config --services | sort)
(cd deploy && COMPOSE_PROFILES=local-db,oidc docker-compose config | grep -E 'OIDC|KC_HOSTNAME')
grep -rn 'DEV_NGINX_PORT\|DEV_PUBLIC_HOST\|DEV_KEYCLOAK_PORT' deploy/ || echo "no DEV_ names left in deploy/"
rm -f deploy/.env
```

Expected: `keycloak` absent from the first list and present in the second; the OIDC URLs resolve against `PUBLIC_HOST`/`KEYCLOAK_PORT`/`HTTP_PORT`; the grep prints `no DEV_ names left in deploy/`.

- [ ] **Step 7: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add deploy/keycloak deploy/compose.yaml deploy/.env.example
git add -u dev/keycloak
git commit -m "feat(deploy): fold Keycloak into an oidc profile, rename DEV_* vars

DEV_PUBLIC_HOST -> PUBLIC_HOST, DEV_NGINX_PORT -> HTTP_PORT,
DEV_KEYCLOAK_PORT -> KEYCLOAK_PORT: these files carried the only
occurrences in the repo, and the same values now serve prod."
```

---

### Task 14: `deploy/README.md` — the one bootstrap document

Merges the useful prose from `dev/README.md`, `docker/README.md`, and `database/README.md`.

**Files:**
- Create: `deploy/README.md`

**Interfaces:**
- Consumes: everything built in Tasks 2–13.
- Produces: the reference the published docs (Task 15) link to for detail.

- [ ] **Step 1: Read the three READMEs being superseded and keep what is still true**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
cat dev/README.md docker/README.md database/README.md
```

Carry forward: anything about hot-reload gotchas, dump handling, and backup expectations. Drop everything about two-stack layering, `host.docker.internal`, and hand-edited nginx.

- [ ] **Step 2: Write `deploy/README.md`**

It must cover, in this order:

1. **What this directory is** — one stack: database, redis, server, client, fileserver. Two doors: `./install.sh` (clients, production build) and `make up` (developers, hot reload).
2. **Prerequisites** — Docker only. Linux and macOS natively, Windows via WSL2. `make` is developer convenience, never required.
3. **The compose binary** — both `docker compose` and `docker-compose` are supported; the scripts resolve which one this host has. Show both forms.
4. **Quick start**, both doors, with the day-2 commands run plainly from `deploy/`.
5. **Layer selection** — the `COMPOSE_FILE` table below, and the rule that setting `COMPOSE_FILE` disables automatic `compose.override.yaml` discovery, so it must name every layer.

   | Entry point | `COMPOSE_FILE` | `COMPOSE_PROFILES` |
   |---|---|---|
   | `./install.sh` | `compose.yaml:compose.local-db.yaml:compose.storage.yaml:compose.prod.yaml` | `local-db` |
   | `make up` | `compose.yaml:compose.override.yaml:compose.local-db.yaml:compose.storage.yaml` | `local-db` |
   | `make prod` | explicit `-f compose.yaml -f compose.storage.yaml -f compose.prod.yaml` | *(none)* |

6. **Why "bundled database" is said twice** — the profile enables the service, the layer adds the health dependency, a compose file layer cannot itself be profile-gated, and `make doctor` checks they agree.
7. **Storage, in two layers** — platform storage (`/storage`, a named volume unless `PLATFORM_STORAGE_PATH` is set) versus image datasets (`storage-mounts.json` → generated mounts, nginx locations, and `EYENED_STORAGE_MOUNTS`). Include the populated example:

   ```json
   {
     "oogergo": "/mnt/oogergo",
     "genr": "/mnt/genr"
   }
   ```

8. **Adding your first dataset** — the four steps: add the key, re-run the entry point, import with that `storage_backend_key` (the `StorageBackend` row is created automatically on import), then `make check-storage`.
9. **Sharing a machine** — `COMPOSE_PROJECT_NAME`, `HTTP_PORT`, `ADMINER_PORT`; no database or redis port published by default; `compose.host-ports.yaml` when you need one.
10. **Migrations** — `make migrate` runs inside the server container; it stays interactive because alembic's own prompt guards a populated database. Fresh installs use `eorm initialize-database`, never `alembic upgrade head` from zero.
11. **Backup and rollback** — `make db-snapshot` / `make db-restore` for data (cold, because MySQL auto-commits DDL per statement); for the application, check out the previous release tag and re-run `./install.sh`. **Images are built from source, so the checkout is the artifact** — which is why clients install from a tag rather than a branch.
12. **`make reset`** — what it deletes and when it refuses.
13. **Per-site deployments** — `compose.<site>.yaml` + `.env.<site>` layered on `compose.prod.yaml`; `<site>` and not `<client>` because `client` already names the frontend service.
14. **Target reference** — one line per make target.
15. **Troubleshooting** — port in use, compose too old, `.env` written by the other entry point, MySQL not becoming healthy: each pointing at the `make doctor` message.

- [ ] **Step 3: Verify every command in the README actually runs**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
grep -oE '^\s*(make [a-z-]+|\./install\.sh|docker-compose [a-z -]+)' deploy/README.md | sort -u
make -n up down logs doctor check-storage 2>&1 | head -20
```

Expected: every `make` target named in the README exists (`make -n` resolves each without error), and no command references a path that is not in the tree.

- [ ] **Step 4: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add deploy/README.md
git commit -m "docs(deploy): one bootstrap document replacing three stack READMEs"
```

---

### Task 15: Published docs, root README, and the worker env template

`docs/` is deployed to GitHub Pages by `.github/workflows/deploy.yml` **on push to `main`**, and `getting_started.mdx` is the page an external adopter actually follows. It currently tells them to `cd eyened-platform/docker`. These rewrites are part of this change, not follow-up work.

**Files:**
- Modify: `docs/src/content/docs/getting_started.mdx`, `docs/src/content/docs/guides/development_setup.mdx`, `docs/src/content/docs/platform_design.mdx`, `docs/src/content/docs/release_notes.mdx`, `README.md`, `worker/.env.example`

**Interfaces:**
- Consumes: the entry points and file layout from Tasks 2–14.
- Produces: published documentation consistent with the tree. **Merge constraint:** these pages and the deletion of `dev/`/`docker/`/`database/` must reach `main` in the **same** merge. A public page cannot be "deprecated" for the reader following it right now.

- [ ] **Step 1: Rewrite the Quick Setup in `getting_started.mdx`**

Replace lines 18–123 (from `## Quick Setup` through the end of `## Accessing the Platform`) with:

````mdx
## Quick Setup

Everything the platform needs — viewer, API, database, Redis, and file server — runs from one
Docker stack.

**Prerequisite: Docker.** That is the whole list. Supported platforms are Linux and macOS
natively, and Windows via WSL2.

1. Clone a release tag. Images are built from your checkout, so the tag *is* the version:

    ```bash
    git clone --branch v2026.07.0 https://github.com/Eyened/eyened-platform.git
    cd eyened-platform
    ```

2. Run the installer:

    ```bash
    ./install.sh
    ```

    It checks your machine, creates `deploy/.env` with freshly generated secrets, builds the
    images, starts the stack, creates the database schema, seeds the builtin form schemas, and
    prints the URL together with a one-time administrator password. Nothing needs to be edited
    by hand.

3. Open the printed URL and sign in as `admin`.

:::caution
The administrator password is printed **once**. Copy it before closing the terminal. More users
can be created from the user interface, or with `eorm create-user`.
:::

### Day-to-day

Run these from the `deploy/` directory. The installer recorded which layers this stack uses, so
plain Compose commands resolve them with no extra flags:

```bash
cd deploy
docker compose logs -f      # follow logs
docker compose down         # stop
docker compose up -d        # start
```

If your Docker installation has the standalone binary rather than the plugin, use
`docker-compose` instead of `docker compose`. The installer prints whichever one your machine has.

### Adding your first dataset

A fresh install has an empty database, therefore no storage backends and no images — a correct
but blank viewer. To point the platform at a directory of images:

1. Add the dataset to `deploy/storage-mounts.json`, mapping a key to its path on this machine:

    ```json
    {
      "my-dataset": "/data/my-dataset"
    }
    ```

2. Re-run `./install.sh`. From that one file it regenerates the container mounts, the nginx
   routes, and the `EYENED_STORAGE_MOUNTS` setting the ORM reads.

3. Import images with `storage_backend_key: "my-dataset"` — see
   [Importing Data](/eyened-platform/importing_data). The storage backend record is created
   automatically on first import, so there is no separate registration step.

4. Confirm the configuration and the database agree:

    ```bash
    make check-storage      # or: deploy/scripts/check-storage.sh
    ```

:::note
For local development with hot reload, see
[Development Setup](/eyened-platform/guides/development_setup).
:::

:::caution
Set up regular backups for both the database and the storage directories. `make db-snapshot NAME=x`
takes a cold snapshot of the bundled database; see `deploy/README.md`.
:::
````

Leave the feature list (lines 1–17) and everything from the `:::tip` about `eyened_orm` onward unchanged.

- [ ] **Step 2: Rewrite `guides/development_setup.mdx`**

Replace the intro and "First-time setup" (lines 6–73) with:

````mdx
The whole platform — viewer, API, nginx, Redis, **and** MySQL — runs from one Docker stack in
`deploy/`, with `server/`, `orm/`, and `client/` bind-mounted for hot reload. There is no separate
database stack to start first.

## Prerequisites

- [Docker](https://www.docker.com/)
- [Git](https://git-scm.com/)
- `make` (developer convenience; clients install without it)

To run `eorm` or `pytest` on the host, install the ORM — see
**[ORM setup](/eyened-platform/orm/getting_started)**.

## First-time setup

```bash
git clone https://github.com/Eyened/eyened-platform.git
cd eyened-platform
make up
```

That is the whole thing. `make up` runs preflight checks, creates `deploy/.env` from the template
with generated secrets, builds the images, starts the stack, and — because the database is empty
on a fresh clone — creates the schema, seeds the builtin form schemas, and creates an `admin`
account whose password it prints once.

### On a machine shared with other developers

Before the first `make up`, or any time afterwards, set these in `deploy/.env` to values nobody
else is using:

| Variable | Purpose |
| --- | --- |
| `COMPOSE_PROJECT_NAME` | Prefix for containers and volumes — makes your stack independent |
| `HTTP_PORT` | The port you open in a browser |
| `ADMINER_PORT` | The bundled database browser |

The bundled MySQL and Redis publish **no** host ports by default, which removes the commonest
source of collisions. If you need one — DBeaver, or a host-side alembic — append
`:compose.host-ports.yaml` to `COMPOSE_FILE` in `deploy/.env` and set `DB_PUBLISH_PORT`.

## Daily use

```bash
make up          # start (also rebuilds and re-bootstraps; safe to repeat)
make logs        # follow logs
make down        # stop
make doctor      # preflight checks on their own
```

The **client** container runs Vite with hot reload; the **server** container runs uvicorn with
`--reload` over the mounted `server/` and `orm/` sources.

## Storage

Platform storage (thumbnails, `segmentations.zarr`) lives at `/storage` inside the container,
backed by this stack's own named volume — a clean clone never writes into shared or production
storage. To attach to shared storage instead, set `PLATFORM_STORAGE_PATH` in `deploy/.env`.

Image datasets are configured in `deploy/storage-mounts.json` alone; re-running `make up`
regenerates the container mounts, the nginx routes, and `EYENED_STORAGE_MOUNTS` from it. Full
detail in `deploy/README.md`.

## Migrations

```bash
make migrate     # alembic upgrade head, inside the server container
```

It stays interactive on purpose: alembic prompts before touching a populated database. Take a
snapshot first — MySQL commits DDL per statement, so a half-applied migration cannot be reliably
undone:

```bash
make db-snapshot NAME=before-migration
make db-restore  NAME=before-migration
```
````

Then update the remaining sections: the OIDC section becomes "add `oidc` to `COMPOSE_PROFILES` in `deploy/.env` and set `PUBLIC_HOST`, then `make up`" (pointing at `deploy/keycloak/README.md`); the load-dump section uses `deploy/scripts/load_dump.sh`; the stale `alembic -x env_file=../../dev/.env upgrade head` line becomes `make migrate`; and the closing tip points at `deploy/README.md` instead of `dev/README.md`.

- [ ] **Step 3: Update `platform_design.mdx`**

Four edits:
- Line 12: `PORT` (set in `docker/.env`, default `80`) → `HTTP_PORT` (set in `deploy/.env`, default `8080`).
- Line 16: `These run from docker/docker-compose.yaml` → `These run from deploy/compose.yaml`.
- Line 31: replace the "not bundled in the main compose stack — run the `database/` stack" paragraph with: MySQL **is** part of the stack, running under the `local-db` profile; point at an external server by removing that profile and the `compose.local-db.yaml` layer and setting `EYENED_DATABASE_*`.
- Line 47: replace "Configure a matching nginx `location /{key}/` and read-only mount on the fileserver for each backend" with: add the key and path to `deploy/storage-mounts.json` and re-run the entry point — the mount, the nginx location, and `EYENED_STORAGE_MOUNTS` are all generated from that one file.

- [ ] **Step 4: Add a release-notes entry**

Insert directly after the frontmatter in `release_notes.mdx`:

```mdx
## Unreleased

### Deployment

- **One Docker stack.** `dev/`, `docker/`, and `database/` are replaced by a single `deploy/`
  directory. Clients install with `./install.sh` (Docker is the only prerequisite); developers
  use `make up`. The database is part of the stack rather than a second compose project.
- **Breaking: environment variables renamed.** `DEV_NGINX_PORT` → `HTTP_PORT`,
  `DEV_PUBLIC_HOST` → `PUBLIC_HOST`, `DEV_KEYCLOAK_PORT` → `KEYCLOAK_PORT`. The same variables
  now serve production, so the `DEV_` prefix was misleading. Existing `.env` files must be
  updated; `deploy/.env.example` is the new template.
- **Storage mounts have one source of truth.** `deploy/storage-mounts.json` generates the
  container bind mounts, the nginx `location` blocks, and `EYENED_STORAGE_MOUNTS`, replacing
  three places that had to be edited in agreement.
- **`eorm` confirmation prompts on database state.** `initialize-database` and `load-dump` ask
  for the typed confirmation code only when the target database contains tables, which is what
  makes an unattended first-run bootstrap possible. A populated database is still gated.
- **Fixed: in-process image reads.** The server container now receives `EYENED_STORAGE_MOUNTS`,
  so Python-side pixel reads (thumbnail regeneration, inference, reports) use local files
  instead of failing in the API adapter. `EYENED_API_USER` was also silently ignored — the
  correct name is `EYENED_API_USERNAME`.
```

- [ ] **Step 5: Update the root `README.md` repository overview**

Add a `deploy` entry describing the unified stack, and change the `dev` and `docker` entries to note that they are superseded by `deploy/` (they are still present until the landing decision in Task 16):

```markdown
***deploy:*** The one Docker stack — database, Redis, server, client, and file server — plus
`install.sh` (client installs) and the `Makefile` targets developers use. Start here.
```

- [ ] **Step 6: Reconcile `worker/.env.example`**

Add `EYENED_STORAGE_MOUNTS`, which inference and thumbnail generation need and the template omits. Insert after the `EYENED_STORAGE_ROOT` line:

```bash
# --- Image datasets — required for inference: without it the worker falls back to
# reading pixels through the API. Same JSON map as deploy/storage-mounts.json produces,
# with paths as they are mounted into THIS container.
# EYENED_STORAGE_MOUNTS={"my-dataset":"/data/my-dataset"}
```

- [ ] **Step 7: Run the mechanical consistency check**

This is the regression test for goal 3, and the one most likely to be forgotten, because nothing in CI fails when a doc goes stale.

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
grep -rn 'DEV_NGINX_PORT\|DEV_PUBLIC_HOST\|DEV_KEYCLOAK_PORT' docs/ README.md || echo "no DEV_ names in docs"
grep -rn 'cd docker\|cd ../database\|docker/\.env\|database/\.env\|dev/\.env\|dev/README\|docker/docker-compose\|database/docker-compose' \
     docs/src/content/docs/ README.md || echo "no old-stack paths in docs"
```

Expected: both lines print the "no ..." message. Anything that shows up is a page this task must also fix — the release-notes history entry describing the old `database/` extraction is the one legitimate exception, since it records what was true at that release.

- [ ] **Step 8: Build the docs site**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation/docs
npm install && npm run build
```

Expected: a successful Astro build with no broken internal links.

- [ ] **Step 9: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add docs/src/content/docs/getting_started.mdx \
        docs/src/content/docs/guides/development_setup.mdx \
        docs/src/content/docs/platform_design.mdx \
        docs/src/content/docs/release_notes.mdx \
        README.md worker/.env.example
git commit -m "docs: rewrite the published setup pages around deploy/

getting_started.mdx is what external adopters follow and is published to
GitHub Pages from main, so it must land in the same merge as the deletion
of the stacks it used to describe."
```

---

### Task 16: Full verification, and the landing decision

The spec's Landing plan is explicit that the cutover shape is chosen **after** the prototype exists, with evidence about what actually breaks. This task produces that evidence and stops.

**Files:**
- Create: `docs/superpowers/plans/2026-07-27-deploy-consolidation-verification.md` (the record)
- Modify: none

**Interfaces:**
- Consumes: everything above.
- Produces: a verification record and a written landing recommendation for the user to decide on.

- [ ] **Step 1: Run the spec's verification matrix**

Work through items 1–24 of the spec's Verification section. Most have already been exercised task by task; run them again end to end against the final tree, and record for each: **pass**, **fail**, or **not run here** with the reason.

Three deserve special attention because they were not fully exercised by earlier tasks:

```bash
# 9. The in-process read bug is actually fixed (needs the shared dev database
#    and real storage mounts, so run this on the shared host):
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation/deploy
docker-compose exec -T server python -c "
from sqlalchemy import select
from eyened_orm import Database, ImageInstance
with Database().get_session() as session:
    image = session.execute(select(ImageInstance).limit(1)).scalar_one()
    print('pixel_array shape:', image.pixel_array.shape)
"

# 17. Attached to the shared dev database, existing images and thumbnails render.

# 24. Regression: the existing test suite still passes.
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
PYTHONPATH=$PWD/orm /home/kdatta/workspace/eyened-platform/dev/.venv/bin/pytest -q
```

Expected for item 9: a shape, not `ValidationError: url missing, username missing`. Expected for item 24: the same pass count as before this work, plus the four tests from Task 1.

Item 22 (macOS or WSL2) cannot be run on this host. If it is not run before merge, **the docs must claim only what was actually exercised** — an untested support matrix is worse than a narrow one, because it fails in the hands of the audience least able to debug it. Either arrange a run on one of those platforms, or narrow the platform statement in `getting_started.mdx` and `deploy/README.md` to what was tested.

- [ ] **Step 2: Update the graph**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
/home/kdatta/workspace/eyened-platform/dev/.venv/bin/graphify update .
```

- [ ] **Step 3: Write the verification record**

`docs/superpowers/plans/2026-07-27-deploy-consolidation-verification.md`, containing:

- A table: verification item → pass / fail / not run → evidence (command and observed output).
- What broke during the three-way verification and what it cost to fix.
- Anything that had to deviate from the spec, and why.

- [ ] **Step 4: Present the landing decision**

The spec deliberately left this open. Present the evidence and a recommendation covering:

- **Additive with deprecation** (add `deploy/`, mark `dev/`/`docker/`/`database/` deprecated, delete in a follow-up PR) versus **a single PR** that adds and deletes together, possibly with an `adopt-env` helper for existing `.env` files.
- The constraint that decides it: the published docs and the deletion must reach `main` in the same merge, since Pages publishes from `main` and a public page cannot be deprecated for the reader following it right now. Additive-with-deprecation buys nothing for that page.
- Reconciliation with open issue #151 and bart's unmerged `origin/docs/clarify-storage-mounts-151`, whose two-layer storage framing this design adopts.
- Coordination cost: `dev/`, `docker/`, and `database/` are almost entirely bart's work and four contributors have branches in flight. Each will need to move to `deploy/.env`; the `DEV_*` renames break their existing files.

**Stop here.** Deleting the old stacks is the user's call, not this plan's.

- [ ] **Step 5: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/deploy-consolidation
git add docs/superpowers/plans/2026-07-27-deploy-consolidation-verification.md
git commit -m "docs(deploy): verification record for the consolidated stack"
```

---

## Notes for the implementer

**Things that look wrong but are deliberate:**

1. **"Use the bundled database" is configured twice** (`local-db` in `COMPOSE_PROFILES` *and* `compose.local-db.yaml` in `COMPOSE_FILE`). A compose file layer is merged unconditionally and cannot itself be profile-gated. Setting one without the other fails unhelpfully in both directions, which is exactly why `doctor` checks the pair. Do not try to "simplify" this by moving `depends_on` into the base — that breaks the external-database case outright.

2. **`make prod` re-lists the storage layer.** An explicit `-f` list overrides `COMPOSE_FILE` from `.env` entirely (verified: with `COMPOSE_FILE=compose.yaml:compose.storage.yaml`, adding `-f compose.yaml -f compose.prod.yaml` yields `base prod` and silently drops `storage`).

3. **The generated nginx snippet is not in `conf.d/`.** The base image includes that directory inside `http{}`, where a `location` block is a startup failure.

4. **`bootstrap.sh` uses `eorm initialize-database`, never `alembic upgrade head`.** Replaying the migration chain from zero is not a path this repo maintains; `initialize-database` runs `create_all` and stamps alembic at head so later upgrades apply only new migrations.

5. **`bootstrap.sh` runs only `alembic current` and `heads`**, both already exempt from `env.py`'s prompt. That is why `orm/migrations/alembic/env.py` needs no change and keeps guarding manual `make migrate` runs.

6. **The admin account is not `EYENED_API_USERNAME`/`EYENED_API_PASSWORD`.** Those name an account the ORM uses to call the API from a host without mounts — a different thing from the human administrator, and conflating them would make one variable mean two things.

**If something must deviate from the spec,** record it in the verification file (Task 16) rather than silently changing behavior. The spec's decisions came from live probing, not defaults.
