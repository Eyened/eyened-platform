# deploy/ — the eyened-platform stack

One stack: database, redis, server, fileserver — plus a `client` container in
development only, see [Where the frontend comes
from](#where-the-frontend-comes-from). Two doors into it:

- **`./eyened install`** — for clients. Builds and runs the production stack
  (built SPA, gunicorn, no source mounts) on a database this stack owns.
  Docker is the only prerequisite.
- **`./eyened up`** — for developers. Builds and runs the development stack
  (vite hot reload, server and orm source bind-mounted) on the same bundled
  database.

Everything below applies to both doors unless it says otherwise. Where a
step is client-only or developer-only, it says so explicitly.

## Prerequisites

Docker only. Nothing else is required to run the stack.

- Linux and macOS are supported natively.
- Windows is supported via WSL2.
- `make` is **not** required, and there is no Makefile. `./eyened` is a plain
  `#!/bin/sh` script at the repository root; the larger pieces it delegates to
  under `deploy/scripts/` can also be run directly (see [Command
  reference](#command-reference)).

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
git clone https://github.com/Eyened/eyened-platform.git
cd eyened-platform
./eyened install
```

**Developers** — run the dev stack:

```bash
git clone https://github.com/Eyened/eyened-platform.git
cd eyened-platform
./eyened up
```

Both doors print an admin password once, on first run, and then a "day-to-day
commands" block. Those commands are run plainly from `deploy/`, with no
wrapper and no `-f` flags — the install already recorded which layers this
stack uses in `deploy/.env`:

```bash
cd deploy
docker compose logs -f
docker compose down
docker compose up -d
```

(or `docker-compose` in place of `docker compose`, per [The compose
binary](#the-compose-binary) above.)

> **Upgrading an existing stack past the dev-client fix:** if you
> already have this stack running from before that change, a plain `up -d`
> is not enough to pick it up — it reuses the existing `client` image, and
> the fix lives in that image's entrypoint. Run `docker compose up -d
> --build` once (or just re-run `./eyened install` / `./eyened up`, which both run
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
| `./eyened install` | `compose.yaml:compose.storage.yaml:compose.prod.yaml` | `local-db` |
| `./eyened up` | `compose.yaml:compose.dev.yaml:compose.storage.yaml` | `local-db` |
| `./eyened prod` | `compose.yaml:compose.storage.yaml:compose.prod.yaml` | *(none)* |

`./eyened install` and `./eyened prod` run the **same layers** and differ only in
the profile. That is deliberate: whether the bundled database runs is one
setting (`local-db` in `COMPOSE_PROFILES`), not two.

Compose declares two profiles, both defined in `deploy/compose.yaml`:

| Profile | Service | What it starts |
|---|---|---|
| `local-db` | `database` | the bundled MySQL |
| `backup` | `xtrabackup` | a `percona/percona-xtrabackup:8.0` one-shot, used by `./eyened backup` and `./eyened restore` (`deploy/scripts/db-backup.sh` / `db-restore.sh`) — never a long-running service. See [Backup and rollback](#backup-and-rollback) |

`deploy/compose.workers.yaml` declares three more, one per GPU model worker:

| Profile | Service |
|---|---|
| `gpu-inference` | `worker-inference` |
| `gpu-cfi-amd` | `worker-cfi-amd` |
| `gpu-layer-segmentation` | `worker-layersegmentation` |

A profile absent from `COMPOSE_PROFILES` means that service simply does not
start — nothing warns you if you forgot one.

Layers append to `COMPOSE_FILE` the same way. The optional ones are:

| Layer | What it adds |
|---|---|
| `compose.host-ports.yaml` | loopback host ports for the database and Redis — see [Sharing a machine](#sharing-a-machine) |
| `compose.oidc.yaml` | the bundled Keycloak |
| `compose.workers.yaml` | the RQ workers — see [Workers](#workers) |

**OIDC.** What you set here is `:compose.oidc.yaml` on `COMPOSE_FILE`,
`KEYCLOAK_PORT` (default `8180`), and `KEYCLOAK_ADMIN_PASSWORD`. The
`EYENED_OIDC_*` values themselves are never derived — they are plain
operator values in `deploy/.env`, the same for the bundled Keycloak and an
external provider.
`./eyened doctor` refuses to build while `compose.oidc.yaml` is enabled and
`KEYCLOAK_ADMIN_PASSWORD` is still a published default: `doctor.sh` has no
warning level, and `./eyened` runs it before anything else, so the run stops
at `preflight failed — nothing was built` (see
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
means rebuilding the fileserver image.** `./eyened install` (and `./eyened prod`)
does this for you every time it runs.

## Compose 2.26 or newer is required

This is not a nicety — `./eyened doctor` refuses to continue below the floor.

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

The container path is canonical. `/storage` inside the container, always;
`compose.yaml` pins it and `deploy/.env` cannot override it. Host locations
appear only in volume mappings — `PLATFORM_STORAGE_PATH` for platform storage,
`storage-mounts.conf` for image datasets. Image records store **relative** keys
resolved through `EYENED_STORAGE_MOUNTS`, so no host path is ever written into
the database and moving the data to a different host is a mount change, not a
migration.

Every configured host path must exist before the stack starts. Docker creates
an empty directory at a missing bind-mount source instead of refusing, which
turns a typo into a healthy stack that reads nothing and writes into limbo.
`./eyened doctor` checks this.

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
every `./eyened install` / `./eyened up` / `./eyened prod` invocation.

**The database's own storage is neither of those two.** `DB_DATA_PATH`
decides where the bundled MySQL keeps its data: unset, it lives in this
stack's own named volume and is deleted along with the stack
(`./eyened reset`); set to an absolute path, it lives there instead and
outlives the stack.

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
2. Re-run the entry point you used before (`./eyened install` or `./eyened up`) —
   this regenerates the mounts and nginx locations and restarts the stack.
3. Import your data with that key as the `storage_backend_key`. The
   `StorageBackend` row is created automatically on import; there is no
   separate registration step.
4. Run `./eyened check-storage` to confirm `storage-mounts.conf` and the
   database's `StorageBackend` rows agree.

## Workers

RQ workers run the image models and generate thumbnails. They are one layer,
`deploy/compose.workers.yaml`, and it serves both deployments — workers beside
the platform, and workers on a separate GPU box. The `worker/` directory holds
only Dockerfiles now.

**Co-located** — the workers on the platform host:

1. Append `:compose.workers.yaml` to `COMPOSE_FILE` in `deploy/.env`.
2. Add a GPU profile to `COMPOSE_PROFILES` if you want a model worker, e.g.
   `local-db,gpu-inference`.
3. `./eyened up`.

They join this project's default network and reach `redis` and the `database`
**by service name**, with nothing published on the host at all.

**The slim ROI worker starts with the layer and needs no profile.** It listens
on `cfi-roi` and on `default` — and `default` is the queue the API enqueues
thumbnail jobs to. Without a consumer for it a stack silently never generates
thumbnails, which is what `deploy/` did until this layer existed. Adding the
layer is the opt-in; there is nothing further to switch on for the common case.

The GPU inference worker defaults to `default,cfi-roi,cfi-keypoints,cfi-odfd,
cfi-quality`, so running it beside the slim one double-consumes two queues.
Set `EYENED_RQ_QUEUES_INFERENCE` in `deploy/.env` to drop them if you want each
job handled once.

**Remote** — the workers on a separate GPU box. Copy the repo there and set, in
that box's `deploy/.env`:

```
COMPOSE_FILE=compose.workers.yaml:compose.storage.yaml
EYENED_REDIS_HOST=<platform host>
EYENED_DATABASE_HOST=<platform host>
PLATFORM_STORAGE_PATH=<absolute path to platform storage on this box>
```

**Do not run `./eyened` on this box.** Nothing rewrites the `COMPOSE_FILE` you
set above — `deploy/.env` is written once and never touched again — so the
hand-set value is safe. `./eyened` still only knows how to build the
*platform* stack, and its preflight does refuse this `.env`: `COMPOSE_FILE`
above names neither `compose.dev.yaml` nor `compose.prod.yaml`, so
`./eyened doctor` reports it as matching no entry point and the run stops
before anything is built (measured). Use the plain `docker compose -f ...`
invocation below instead — it needs no platform-stack preflight to do the
right thing here.

Fill in `storage-mounts.conf` the same way as on the platform host, run
`deploy/scripts/gen-storage.sh`, then:

```bash
docker compose -f deploy/compose.workers.yaml -f deploy/compose.storage.yaml \
  up -d --build
```

There is **no second env file**: compose reads `.env` from the compose file's
own directory rather than the working directory, so `deploy/.env` is picked up
from anywhere. Image datasets are configured exactly once, the same way in both
deployments — `storage-mounts.conf` → `gen-storage.sh` → `compose.storage.yaml`
— and `COMPOSE_FILE` is what decides which services that generated layer hands
the mounts to.

**`PLATFORM_STORAGE_PATH` is required on a remote box, and nothing enforces
it.** Its default is this stack's own named volume; on another machine that is
a new, empty one. The workers would start, report healthy, and write thumbnails
and segmentations where nothing on either host can read them. `./eyened doctor`
checks configured storage paths, but it runs on the platform host, not on the
GPU box — set it by hand there.

**Nothing in `compose.workers.yaml` may gain a `depends_on`.** Standalone,
compose refuses the entire project before starting anything —
`service "worker-cfi-roi" depends on undefined service "redis": invalid compose
project` — because `redis` is declared in `compose.yaml`, which the remote path
does not load. `required: false` does not rescue it: that flag covers a service
that is *declared* and profile-disabled (`compose.yaml`'s external-database
toggle), not one that is not declared at all. The tidy-up is invisible
co-located and breaks only the remote path, so CI asserts the standalone
project resolves. Nothing is lost: RQ retries its connection and every worker
restarts unless stopped.

To rebuild one worker image:

```bash
cd deploy
docker compose -f compose.workers.yaml --profile gpu-cfi-amd build worker-cfi-amd
```

## Sharing a machine

On a host shared with other developers, set these in `deploy/.env` to values
nobody else is using — all three are already present in `.env.example`:

- `COMPOSE_PROJECT_NAME` — isolates containers, volumes and networks per
  stack.
- `HTTP_PORT` (default `8080`) — the platform's own port.
- `KEYCLOAK_PORT` (default `8180`) — only published when `compose.oidc.yaml`
  is in `COMPOSE_FILE`.

No database or redis port is published by default — that is the commonest
source of collisions between developers on one machine. If you need one (for
DBeaver, or a host-side alembic), append `:compose.host-ports.yaml` to
`COMPOSE_FILE` and set `DB_PUBLISH_PORT` / `REDIS_PUBLISH_PORT` to free
ports; both bind to `127.0.0.1` only.

Keycloak is off unless `compose.oidc.yaml` is in `COMPOSE_FILE`, and it
**binds every interface** (`KEYCLOAK_BIND`, default `0.0.0.0`). That is not
an oversight: the server container reaches Keycloak's metadata document
*through the host*, so confining it to loopback makes OIDC login fail while
every container still reports healthy. Because the admin console is
therefore reachable by anyone who can reach the port, `KEYCLOAK_ADMIN_PASSWORD`
is not optional: `./eyened doctor` fails while it is absent, empty, `admin` or
`change_me` and `compose.oidc.yaml` is enabled, so the stack will not build
until you set it.

## Migrations

```bash
./eyened migrate
```

Runs `alembic upgrade head` inside the server container and stays
interactive on purpose — alembic's own confirmation prompt is what still
guards a populated database against the wrong migration being applied.

**Fresh installs never run this.** `./eyened install` and `./eyened up` initialize a
brand-new database with `eorm initialize-database`, not by replaying the
whole alembic chain from an empty schema — that is not a path this repo
maintains. `./eyened migrate` is for applying new migrations to a database that
already has a schema.

## Backup and rollback

| Case | Tool |
|---|---|
| The bundled database — live, fast, byte-exact | `./eyened backup <dir>` / `./eyened restore <dir>` |
| Any database including an external one; portable across MySQL versions | `eorm save-dump` / `eorm load-dump` (a HOST tool — needs `mysqlsh` installed) |

`./eyened backup` runs Percona XtraBackup in a one-shot container under the
`backup` profile. The database keeps serving throughout. The output is a raw
InnoDB datadir, so the machine you restore onto must run a compatible MySQL
8.0 — true by construction here, since the stack pins `mysql:8.0.46`. Add
`-t` for a single `.tgz`; `./eyened restore` accepts either form.

A relative `<dir>` is resolved under `deploy/` — `deploy/backups/` is the
suggested one and is gitignored. `<dir>` is refused outright if it resolves
inside the checkout and git does **not** ignore it, so a backup (a raw
MySQL datadir) can never end up in `git add -A`'s path in this public repo;
pass an absolute path outside the checkout, or a gitignored one, instead.

`./eyened restore` stops the database, replaces the entire datadir, and starts
it again. There is no undo. An interrupt is safe: it leaves the database
stopped and tells you to re-run.

`eorm save-dump` / `eorm load-dump` are a different mechanism — a logical dump
via `mysqlsh`, with a `--legacy-sql` mysqldump fallback — and the tool for a
database this stack does not own. They run on the HOST, not in a container:
`Dockerfile.server` carries no MySQL client at all, so neither mode works
inside the stack. **`mysqlsh` is a host prerequisite for this path** and is not
installed by anything here.

For the application itself: check out the commit-ish you moved *from* and
re-run `./eyened install`. **Images are built from source, so the checkout is
the artifact** — there is nothing else to roll back, and equally nothing that
rolls back on its own. Record the revision (`git rev-parse --short HEAD`)
before you move, or there is nothing to return to.

> **On an external database** — a site deployment (`./eyened prod`, no
> `local-db` profile) — `./eyened backup` does **not** apply. It backs up
> this stack's own datadir, and there isn't one. Take a backup with that
> database server's own tooling, or `eorm save-dump`, **before** running
> `./eyened migrate`. MySQL commits DDL per statement, so a half-applied
> migration cannot be reliably rolled back with `alembic downgrade`.

## `./eyened reset`

Stops the stack and **deletes its volumes** — the bundled database and
platform storage. It asks for confirmation by making you type the exact
`COMPOSE_PROJECT_NAME` back.

It refuses outright, rather than guess, whenever this stack does not clearly
own what it would be deleting — or whenever it cannot tell:

- `deploy/.env` does not exist — there is no stack here to reset, and nothing
  to check ownership against. (Without this check every other guard below
  reads empty and the `COMPOSE_PROFILES` one fires first, diagnosing a
  configuration that was never created.)
- `PLATFORM_STORAGE_PATH` is set — this stack is attached to storage it does
  not own.
- `DB_DATA_PATH` is set — `/var/lib/mysql` is then a bind mount rather than
  this stack's named volume, so `down -v` would leave the entire database
  intact. This one *under*-deletes rather than over-deletes, which is not
  data loss but does mean reset cannot do what its name says: the next
  `./eyened install` would find the old database still there. Delete that
  directory by hand if you really do mean to destroy the durable copy.
- `COMPOSE_PROFILES` does not contain `local-db` — this stack uses an
  external database; reset only removes volumes this stack owns, and the
  external database would be untouched, which is not what "reset" implies.
- `EYENED_DATABASE_HOST` is not the bundled `database` service.
- `COMPOSE_PROJECT_NAME` is unset — reset needs a project name to confirm
  against.
- `docker compose config` does not return a volume list — the confirmation
  prompt names the volumes compose itself resolves, rather than rebuilding
  their names by hand, and reset will not run `down -v` against a list it
  could not read.

## Per-site deployments

For more than one site deployment from a single checkout, the convention is
`compose.<site>.yaml` (named `<site>`, not `<client>` — `client` already
names the frontend service the dev layer adds) layered on top of
`compose.prod.yaml`, together with a `.env.<site>` holding that site's
configuration. Neither file is generated or managed by the deploy scripts:
append the site's compose file to `COMPOSE_FILE` the same way
`compose.host-ports.yaml` is documented above, and keep the site's `.env.<site>`
alongside `deploy/.env` (both are already covered by `deploy/.env.*` in
`.gitignore`), copying the one you want into `deploy/.env` before running
`./eyened prod` for that site.

## Command reference

Every command `./eyened` accepts. Run them from anywhere: `./eyened` resolves
its own location, and so does every script it calls.

| Command | Implemented in | What it does |
|---|---|---|
| `./eyened install` | `eyened` | the client install: production stack on a database this stack owns. |
| `./eyened up` | `eyened` | the developer stack — hot reload, source mounted, bundled database. |
| `./eyened prod` | `eyened` | a site deployment against an external database. |
| `./eyened down` | `eyened` | stop this stack. Extra arguments go through to compose. |
| `./eyened logs` | `eyened` | follow logs. Extra arguments go through to compose. |
| `./eyened doctor [dev\|client]` | `deploy/scripts/doctor.sh` | preflight checks, building nothing. |
| `./eyened migrate` | `eyened` | `alembic upgrade head` inside the server container, interactively. |
| `./eyened db-shell` | `eyened` | a MySQL shell in the bundled database. |
| `./eyened check-storage` | `eyened` | report configured mounts with no `StorageBackend` row, and vice versa. |
| `./eyened backup <dir> [-t]` | `deploy/scripts/db-backup.sh` | hot backup of the bundled database — see [Backup and rollback](#backup-and-rollback). |
| `./eyened restore <dir\|backup.tgz>` | `deploy/scripts/db-restore.sh` | restore one. |
| `./eyened reset` | `eyened` | stop this stack and delete its volumes. Guarded; asks for confirmation. |
| `./eyened help` | `eyened` | the list above, at the terminal. |

**`make` is not a prerequisite, and there is no Makefile.** `./eyened` is one
`#!/bin/sh` file at the repository root and needs nothing but a POSIX shell
and Docker. It is also the only entry point: the separate installer and the
four thin scripts that used to sit beside it are now subcommands of it.

`./eyened down` and `./eyened logs` hold no machinery: they are `docker
compose` (or `docker-compose`) run from `deploy/`, so `cd deploy && docker
compose down` is equally correct — see [The compose
binary](#the-compose-binary). The three delegated scripts are ordinary
`#!/bin/sh` files and can still be invoked directly; `./eyened <command>` is
the supported spelling.

## Troubleshooting

- **Port already in use.** `./eyened doctor` checks `HTTP_PORT` and names the
  fix (pick a free port in `deploy/.env`).
- **`compose.oidc.yaml` is enabled and `KEYCLOAK_BIND` is loopback.**
  `./eyened doctor` **fails** on this — it is not advisory, and nothing is
  built. The server container reaches Keycloak's metadata document *through
  the host*, not over the compose network, so a loopback bind leaves token
  exchange failing while every container still reports healthy. The fix
  doctor prints is to leave `KEYCLOAK_BIND` unset (`0.0.0.0`) and confine the
  console with `KEYCLOAK_ADMIN_PASSWORD` instead.
- **`compose.oidc.yaml` is enabled and `KEYCLOAK_ADMIN_PASSWORD` is still the
  default.** Also a `./eyened doctor` failure, for the same reason: compose
  defaults it to `admin`, so absent, empty, `admin` and `change_me` all mean
  the Keycloak admin console comes up on `admin`/`admin` — and that console
  is the identity provider for every account on the platform. Set it in
  `deploy/.env` to a long random value.
- **Compose older than 2.26.** `./eyened doctor` refuses to continue and names
  the required upgrade — see [Compose 2.26 or newer is
  required](#compose-226-or-newer-is-required).
- **`deploy/.env` was written by the other entry point.** `./eyened doctor`
  detects a dev-mode `.env` under `./eyened install` (or vice versa). Because
  `.env` is written once and never rewritten, the fix is to delete it and
  re-run — that is what switching between the two stacks means. Deleting it
  keeps your data; `./eyened reset` is what deletes that.
- **`COMPOSE_FILE` names both `compose.dev.yaml` and `compose.prod.yaml`.**
  Compose accepts this silently — it does not error, and does not warn —
  but the two layers disagree about which image serves the client and which
  nginx config it uses. `deploy/scripts/doctor.sh` catches it; the fix it
  gives is to delete `deploy/.env` and re-run, or to edit `COMPOSE_FILE` by
  hand to name only one of the two layers.
- **MySQL never becomes healthy.** Check `docker compose logs database`;
  `./eyened doctor` cannot detect this ahead of time since it only checks
  configuration, not runtime health.
- **`duplicate location "/"` at nginx startup.** This means `client.d/` was
  hand-edited or has more than one file mounted at
  `/etc/nginx/client.d/client.conf` — the layers each mount exactly one file
  onto that fixed name for this reason. Do not add files to `client.d/`
  directly; the dev and prod layers already pick the right one.
