# deploy/ — the eyened-platform stack

One stack: database, redis, server, client, fileserver. Two doors into it:

- **`./install.sh`** — for clients. Builds and runs the production stack
  (built SPA, gunicorn, no source mounts) on a database this stack owns.
  Docker is the only prerequisite.
- **`make up`** — for developers. Builds and runs the development stack
  (vite hot reload, server and orm source bind-mounted) on the same bundled
  database.

Everything below applies to both doors unless it says otherwise. Where a
step is client-only or developer-only, it says so explicitly.

## Prerequisites

Docker only. Nothing else is required to run the stack.

- Linux and macOS are supported natively.
- Windows is supported via WSL2.
- `make` is a developer convenience — a shorter way to invoke the scripts
  under `deploy/scripts/`. It is never required: `./install.sh` does not use
  it, and every `make` target has an equivalent direct script invocation
  (see [Target reference](#target-reference)).

## The compose binary

The stack works with either the `docker compose` plugin or the standalone
`docker-compose` binary. `deploy/scripts/lib.sh` resolves which one this
host has (`docker compose` first, `docker-compose` as a fallback) and every
script uses that resolved binary — nothing here hardcodes either spelling.
Wherever a command below is shown as `docker compose ...`, `docker-compose
...` works identically if that is what your host has.

## Quick start

**Clients** — install the platform:

```bash
git clone --branch <tag> https://github.com/Eyened/eyened-platform.git
cd eyened-platform
./install.sh
```

**Developers** — run the dev stack:

```bash
git clone https://github.com/Eyened/eyened-platform.git
cd eyened-platform
make up
```

Both doors print an admin password once, on first run, and then a "day-to-day
commands" block. Those commands are run plainly from `deploy/`, with no
`make` and no `-f` flags — the install already recorded which layers this
stack uses in `deploy/.env`:

```bash
cd deploy
docker compose logs -f
docker compose down
docker compose up -d
```

(or `docker-compose` in place of `docker compose`, per [The compose
binary](#the-compose-binary) above.)

> **Upgrading an existing stack past the dev-client fix (Task 12b):** if you
> already have this stack running from before that change, a plain `up -d`
> is not enough to pick it up — it reuses the existing `client` image, and
> the fix lives in that image's entrypoint. Run `docker compose up -d
> --build` once (or just re-run `./install.sh` / `make up`, which both run
> `up -d --build` for you), then plain `up -d` is correct again for every
> start after that.

## Layer selection

`COMPOSE_FILE` in `deploy/.env` is a colon-separated list of compose files.
It must name **every** layer in play — nothing is discovered implicitly.
(That's also why the dev layer is named `compose.dev.yaml` and not
`compose.override.yaml`: the latter is a name Compose auto-loads on its own,
which would defeat the point.)

| Entry point | `COMPOSE_FILE` | `COMPOSE_PROFILES` |
|---|---|---|
| `./install.sh` | `compose.yaml:compose.storage.yaml:compose.prod.yaml` | `local-db` |
| `make up` | `compose.yaml:compose.dev.yaml:compose.storage.yaml` | `local-db` |
| `make prod` | `compose.yaml:compose.storage.yaml:compose.prod.yaml` | *(none)* |

`./install.sh` and `make prod` run the **same layers** and differ only in
the profile. That is deliberate: whether the bundled database runs is one
setting (`local-db` in `COMPOSE_PROFILES`), not two.

Compose declares four profiles, all defined in `deploy/compose.yaml`:

| Profile | Where | What it starts |
|---|---|---|
| `local-db` | `compose.yaml:27` | the bundled MySQL |
| `tools` | `compose.yaml:62` | adminer, a database browser — off by default, see [Sharing a machine](#sharing-a-machine) |
| `backup` | `compose.yaml:77` | the `percona/xtrabackup` one-shot behind `make db-snapshot` / `make db-restore` — never a long-running service |
| `oidc` | `compose.yaml:241` | Keycloak, the bundled development OIDC provider |

Profiles compose: a developer who wants Keycloak *and* the bundled database
sets `COMPOSE_PROFILES=local-db,oidc`. A profile absent from
`COMPOSE_PROFILES` means those services simply do not start — nothing warns
you if you forgot one.

**OIDC.** What you set here is the `oidc` profile, `KEYCLOAK_PORT` (default
`8180`), and `KEYCLOAK_ADMIN_PASSWORD`. Note that `PUBLIC_HOST=localhost`
together with `oidc` draws a `make doctor` warning (see
[Troubleshooting](#troubleshooting)). For realm and client setup, see
**[`deploy/keycloak/README.md`](keycloak/README.md)** — that document is the
source of truth for OIDC configuration and is not repeated here.

## Where the frontend comes from

In development, `compose.dev.yaml` adds a `client` container that runs vite
with hot reload, and `fileserver` proxies `/` to it
(`deploy/nginx/client.d/dev.conf`). In production there is **no client
container at all**: the frontend is built with `adapter-static` and the
resulting static SPA is baked directly into the fileserver image by
`deploy/Dockerfile.fileserver`, served straight off disk
(`deploy/nginx/client.d/prod.conf`).

This is the one `location /` that differs between the two stacks; everything
else in `deploy/nginx/default.conf.template` (the API proxy, thumbnails,
per-dataset storage locations) is identical in both.

Consequence worth stating explicitly: **changing frontend code in production
means rebuilding the fileserver image.** `./install.sh` (and `make prod`)
does this for you every time it runs.

## Compose 2.26 or newer is required

This is not a nicety — `make doctor` refuses to continue below the floor.

The server's dependency on the bundled database is expressed as
`depends_on: database: condition: service_healthy, required: false`, so that
the *same* layer works whether or not `local-db` is in `COMPOSE_PROFILES`.
Compose versions older than 2.24 reject `required: false` outright; versions
2.24–2.25 accept it but **silently drop the dependency**. In that case the
server starts racing MySQL instead of waiting for it, and crash-loops on
first boot with nothing in the logs naming the cause. 2.26 is the first
version that makes an *unintended* omission of `required: false` a loud
error instead of that same silent failure — which is also why the floor is
2.26 and not 2.24.

## Storage, in two layers

**Platform storage** (thumbnails and `segmentations.zarr`) is always
`/storage` inside the containers. By default that is this stack's own named
volume — a clean clone writes nothing outside itself. Set
`PLATFORM_STORAGE_PATH` in `deploy/.env` to an absolute host path to put it
on storage you control instead.

**Image datasets** are configured separately, in `deploy/storage-mounts.conf`
— one `<StorageBackend.Key>  <absolute path>` pair per line:

```
# <StorageBackend.Key>  <absolute path on this host>
oogergo  /mnt/oogergo
genr     /mnt/genr
```

`deploy/scripts/gen-storage.sh` generates everything from that file: the
container bind mounts and `EYENED_STORAGE_MOUNTS` (`compose.storage.yaml`),
and the nginx locations (`nginx/storage.d/storage.conf`). It runs as part of
every `./install.sh` / `make up` / `make prod` invocation.

**The database's own storage is neither of those two.** `DB_DATA_PATH`
decides where the bundled MySQL keeps its data: unset, it lives in this
stack's own named volume and is deleted along with the stack (`make
reset`); set to an absolute path, it lives there instead and outlives the
stack.

Wherever `DB_DATA_PATH` points at storage that outlives the stack, **the
database passwords must be supplied by hand.** First run generates
`MYSQL_ROOT_PASSWORD` and `EYENED_DATABASE_PASSWORD` whenever `deploy/.env`
is absent — and a freshly generated password will not open a database that
is already sitting on that disk. This presents as a config bug (wrong
password) rather than the lifecycle mistake it actually is (a new `.env`
pointed at old data), so if you are attaching `DB_DATA_PATH` to existing
data, set `MYSQL_ROOT_PASSWORD` and `EYENED_DATABASE_PASSWORD` in
`deploy/.env` to the values that database already uses, before first run.

## Adding your first dataset

1. Add a `<key> <absolute path>` line to `deploy/storage-mounts.conf`.
2. Re-run the entry point you used before (`./install.sh` or `make up`) —
   this regenerates the mounts and nginx locations and restarts the stack.
3. Import your data with that key as the `storage_backend_key`. The
   `StorageBackend` row is created automatically on import; there is no
   separate registration step.
4. Run `make check-storage` to confirm `storage-mounts.conf` and the
   database's `StorageBackend` rows agree.

## Sharing a machine

On a host shared with other developers, set these in `deploy/.env` to values
nobody else is using — all four are already present in `.env.example`:

- `COMPOSE_PROJECT_NAME` — isolates containers, volumes and networks per
  stack.
- `HTTP_PORT` (default `8080`) — the platform's own port.
- `ADMINER_PORT` (default `8081`) — only published when `tools` is in
  `COMPOSE_PROFILES`.
- `KEYCLOAK_PORT` (default `8180`) — only published when `oidc` is in
  `COMPOSE_PROFILES`.

No database or redis port is published by default — that is the commonest
source of collisions between developers on one machine. If you need one (for
DBeaver, or a host-side alembic), append `:compose.host-ports.yaml` to
`COMPOSE_FILE` and set `DB_PUBLISH_PORT` / `REDIS_PUBLISH_PORT` to free
ports; both bind to `127.0.0.1` only.

Adminer is behind the `tools` profile and off by default: it is a database
admin UI, and an installed platform should not publish one unless someone
asked for it. Keycloak is likewise off unless `oidc` is in
`COMPOSE_PROFILES`.

## Migrations

```bash
make migrate
```

Runs `alembic upgrade head` inside the server container and stays
interactive on purpose — alembic's own confirmation prompt is what still
guards a populated database against the wrong migration being applied.

**Fresh installs never run this.** `./install.sh` and `make up` initialize a
brand-new database with `eorm initialize-database`, not by replaying the
whole alembic chain from an empty schema — that is not a path this repo
maintains. `make migrate` is for applying new migrations to a database that
already has a schema.

## Backup and rollback

```bash
make db-snapshot NAME=<name>
make db-restore NAME=<name>
```

Data snapshots are **cold** (the database is stopped for the duration):
MySQL commits DDL per statement, so a half-applied migration cannot be
reliably rolled back with `alembic downgrade`, and `db-snapshot` /
`db-restore` are the actual safety net for `make migrate`.

For the application itself: check out the previous release tag and re-run
`./install.sh`. **Images are built from source, so the checkout is the
artifact** — this is also why clients install from a tag rather than a
branch.

> **On an external database** — a site deployment (`make prod`, no
> `local-db` profile) — `make db-snapshot` does **not** apply. It snapshots
> this stack's own volume, and there isn't one. Take a backup with that
> database server's own tooling **before** running `make migrate`. MySQL
> commits DDL per statement, so a half-applied migration cannot be reliably
> rolled back with `alembic downgrade`.

## `make reset`

Stops the stack and **deletes its volumes** — the bundled database and
platform storage. It asks for confirmation by making you type the exact
`COMPOSE_PROJECT_NAME` back.

It refuses outright, rather than guess, when this stack does not clearly own
what it would be deleting:

- `PLATFORM_STORAGE_PATH` is set — this stack is attached to storage it does
  not own.
- `COMPOSE_PROFILES` does not contain `local-db` — this stack uses an
  external database; reset only removes volumes this stack owns, and the
  external database would be untouched, which is not what "reset" implies.
- `EYENED_DATABASE_HOST` is not the bundled `database` service.
- `COMPOSE_PROJECT_NAME` is unset — reset needs a project name to confirm
  against.

## Per-site deployments

For more than one site deployment from a single checkout, the convention is
`compose.<site>.yaml` (named `<site>`, not `<client>` — `client` already
names the frontend service in the base stack) layered on top of
`compose.prod.yaml`, together with a `.env.<site>` holding that site's
configuration. Neither file is generated or managed by the deploy scripts:
append the site's compose file to `COMPOSE_FILE` the same way
`compose.host-ports.yaml` is documented above, and keep the site's `.env.<site>`
alongside `deploy/.env` (both are already covered by `deploy/.env.*` in
`.gitignore`), copying the one you want into `deploy/.env` before running
`make prod` for that site.

## Target reference

Every target the Makefile declares:

| Target | What it does |
|---|---|
| `make install` | the client install (production stack, bundled database). Alias for `./install.sh`. |
| `make doctor` | preflight checks without building anything. |
| `make up` | the developer stack — hot reload, source mounted, bundled database. |
| `make down` | stop this stack. |
| `make logs` | follow logs. |
| `make prod` | a site deployment against an external database. |
| `make migrate` | apply pending migrations inside the server container. |
| `make db-shell` | a MySQL shell in the bundled database. |
| `make reset` | stop this stack and delete its volumes. Guarded; asks for confirmation. |
| `make check-storage` | report configured mounts with no `StorageBackend` row, and vice versa. |
| `make db-snapshot NAME=x` | cold snapshot of the bundled database volume. |
| `make db-restore NAME=x` | restore a snapshot taken by `db-snapshot`. |
| `make help` | list the targets above (and their one-line descriptions) at the terminal. |
| `make gen-openapi` | regenerate `client/src/types/openapi.json` from the server's schema. Not listed by `make help`. |
| `make gen-types` | `gen-openapi`, then generate `client/src/types/openapi.ts` via `openapi-typescript`. Not listed by `make help`. |
| `make gen-client-types` | `gen-types`, then print the generated file's path. Not listed by `make help`. |

## Troubleshooting

- **Port already in use.** `make doctor` checks `HTTP_PORT` and names the
  fix (pick a free port in `deploy/.env`).
- **Compose older than 2.26.** `make doctor` refuses to continue and names
  the required upgrade — see [Compose 2.26 or newer is
  required](#compose-226-or-newer-is-required).
- **`deploy/.env` was written by the other entry point.** `make doctor`
  detects a dev-mode `.env` under `./install.sh` (or vice versa) and tells
  you to either use the matching entry point or remove `deploy/.env` to
  start over.
- **`COMPOSE_FILE` names both `compose.dev.yaml` and `compose.prod.yaml`.**
  Compose accepts this silently — it does not error, and does not warn —
  but the two layers disagree about which image serves the client and which
  nginx config it uses. `deploy/scripts/doctor.sh:173-188` is what actually
  catches it; the fix it gives is to remove `deploy/.env` and let
  `./install.sh` or `make up` write it fresh, or to edit `COMPOSE_FILE` by
  hand to name only one of the two layers.
- **MySQL never becomes healthy.** Check `docker compose logs database`;
  `make doctor` cannot detect this ahead of time since it only checks
  configuration, not runtime health.
- **`duplicate location "/"` at nginx startup.** This means `client.d/` was
  hand-edited or has more than one file mounted at
  `/etc/nginx/client.d/client.conf` — the layers each mount exactly one file
  onto that fixed name for this reason. Do not add files to `client.d/`
  directly; the dev and prod layers already pick the right one.
