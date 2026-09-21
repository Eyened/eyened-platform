# deploy/ — the eyened-platform stack

One compose project: `database` (MySQL, optional), `redis`, `init`, `server` and `fileserver`
(nginx), plus layers for development, workers, OIDC and image datasets. Plain `docker compose`
is the whole interface. `deploy/.env` chooses the layers.

Requires Docker with Compose 2.26 or newer (`docker compose version`); older versions reject or
silently ignore `depends_on: required: false`.

## First run

```bash
git clone https://github.com/Eyened/eyened-platform.git
cd eyened-platform/deploy
cp .env.example .env    # then fill the five secrets, each with: openssl rand -hex 32
docker compose up -d --build
```

Open `http://localhost:8080` and sign in as `admin` with `EYENED_API_ADMIN_PASSWORD`.

On every `up`, the one-shot `init` service runs `eorm bootstrap` before the server starts:

- empty database: create the schema and seed the builtin form schemas;
- schema behind the code: report the pending migrations and carry on, leaving the schema alone.
  `EYENED_AUTO_MIGRATE=true` applies them instead, on every `up`;
- no accounts at all: create `EYENED_API_ADMIN_USERNAME` as administrator with
  `EYENED_API_ADMIN_PASSWORD`.

It never changes an existing account. `docker compose logs init` shows what it did.

## Stacks

| Stack | `COMPOSE_FILE` | `COMPOSE_PROFILES` |
|---|---|---|
| Production, bundled database | `compose.yaml:compose.prod.yaml` | `local-db` |
| Development (hot reload, source mounted) | `compose.yaml:compose.dev.yaml` | `local-db` |
| Production, external database | `compose.yaml:compose.prod.yaml` | *(empty)* |

For an external database, also set `EYENED_DATABASE_HOST`, `_PORT`, `_USER`, `_PASSWORD` and
`_DATABASE`. The account needs DDL rights, because `init` runs the migrations.

Optional layers are appended to `COMPOSE_FILE`:

| Layer | Adds |
|---|---|
| `compose.storage.yaml` | image datasets — see [Image datasets](#image-datasets) |
| `compose.workers.yaml` | RQ workers — see [Workers](#workers) |
| `compose.oidc.yaml` | bundled Keycloak — see [keycloak/README.md](keycloak/README.md) |
| `compose.host-ports.yaml` | MySQL and Redis on `127.0.0.1` (`DB_PUBLISH_PORT`, `REDIS_PUBLISH_PORT`) |

On a host shared with other stacks, give each its own `COMPOSE_PROJECT_NAME` and `HTTP_PORT`.
In production the SPA is built into the fileserver image, so a frontend change needs `--build`.

## Day-to-day

Run from `deploy/`.

| Task | Command |
|---|---|
| Start, or apply `.env` changes | `docker compose up -d` |
| Follow logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Upgrade | `git pull && docker compose up -d --build` |
| Migrate (`up` does not) | `docker compose run --rm -e EYENED_AUTO_MIGRATE=true init` |
| Run an `eorm` command | `docker compose exec server eorm <command>` |
| MySQL shell | `docker compose exec database sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'` |
| Delete the stack **with its database and platform storage** | `docker compose down -v` |

Back up before migrating: MySQL cannot roll back DDL. An upgrade is `git pull && docker compose
up -d --build`, which leaves the schema alone, then the migrate command above once you are ready.
Until it runs, the new code is talking to the old schema. To roll back, check out the previous
commit, restore the backup, then `docker compose up -d --build`.

A database from before the August 2026 migration squash carries a revision alembic cannot
find, and `init` fails on it. Follow `docs/runbooks/2026-08-20-alembic-squash-cutover.md`.

## Image datasets

Each dataset is mounted read-only at `/data/<key>`, where `<key>` is its `StorageBackend.Key`.

1. `cp compose.storage.example.yaml compose.storage.yaml`, and list each dataset as
   `- /host/path:/data/<key>:ro`.
2. With `:compose.workers.yaml` also in `COMPOSE_FILE`, uncomment the worker entries in
   `compose.storage.yaml`. Workers read the datasets directly, so without their mounts every
   thumbnail and inference job fails; a worker now refuses to start rather than fail silently.
3. In `.env`, append `:compose.storage.yaml` to `COMPOSE_FILE` and set
   `EYENED_STORAGE_MOUNTS={"<key>":"/data/<key>"}`, one entry per dataset.
4. `docker compose up -d`.

Platform storage (thumbnails, segmentations) is a Docker volume unless `PLATFORM_STORAGE_PATH`
names a host path.

## Workers

Append `:compose.workers.yaml` to `COMPOSE_FILE`. The CPU worker `worker-cfi-roi` starts with
the layer and consumes `default`, the thumbnail queue. GPU workers also need a profile in
`COMPOSE_PROFILES`: `gpu-inference`, `gpu-cfi-amd` or `gpu-layer-segmentation`.
`worker-inference` also consumes `default` and `cfi-roi` unless `EYENED_RQ_QUEUES_INFERENCE`
narrows it. With image datasets, uncomment the worker entries in `compose.storage.yaml` — see
"Image datasets" above.

On a separate GPU host:

1. Clone the repository and `cp .env.example .env` in `deploy/`.
2. In that `.env`, set `COMPOSE_FILE=compose.workers.yaml` (add `:compose.storage.yaml` for
   datasets, keeping only the worker entries), the GPU profiles, `EYENED_REDIS_HOST`, `_PORT`
   and `_PASSWORD`, `EYENED_DATABASE_HOST`, `_PORT` and `_PASSWORD`, `EYENED_STORAGE_MOUNTS`,
   and `PLATFORM_STORAGE_PATH`. The last is required: without it results land in a new, empty
   volume.
3. On the platform host, publish MySQL and Redis on an address the GPU host can reach, with a
   site file used instead of `compose.host-ports.yaml` (that one binds loopback only):

   ```yaml
   # compose.site.yaml, appended to COMPOSE_FILE
   services:
     database:
       ports: ["<address>:13306:3306"]
     redis:
       ports: ["<address>:16379:6379"]
   ```

   Docker-published ports bypass ufw, so bind to an address only the GPU host can reach.
4. `docker compose up -d --build` on the GPU host.

## Backup and restore

Hot backup of the bundled database with XtraBackup; the database keeps serving. Backups go to
`BACKUP_PATH` (default `deploy/backups`, gitignored).

```bash
docker compose run --rm xtrabackup 'xtrabackup --backup --host=database --user=root --password="$MYSQL_ROOT_PASSWORD" --target-dir=/backup/2026-09-18 && xtrabackup --prepare --target-dir=/backup/2026-09-18'
```

Restore replaces the whole database. There is no undo.

```bash
docker compose stop server database
docker compose run --rm xtrabackup 'rm -rf /var/lib/mysql/* && xtrabackup --copy-back --target-dir=/backup/2026-09-18 --datadir=/var/lib/mysql && chown -R 999:999 /var/lib/mysql'
docker compose up -d
```

An XtraBackup copy opens only on MySQL 8.4. Restoring on another machine brings the source's
MySQL accounts, so first copy `MYSQL_ROOT_PASSWORD` and `EYENED_DATABASE_PASSWORD` from the
source's `.env`.

Portable across MySQL versions:

```bash
docker compose exec -T database sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE"' | gzip > eyened.sql.gz
gunzip -c eyened.sql.gz | docker compose exec -T database sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
```

Back up an external database with that server's own tooling. Back up platform storage
(`PLATFORM_STORAGE_PATH`, or the `platform_storage` volume) with the site's file backup.

## Moving an existing database into this stack

This is an outage: the old database stays down until the new stack serves.

1. Stop the old stack, keeping its volume:

   ```bash
   cd /path/to/old-checkout/database
   docker compose config | grep '^name:'   # the project name
   docker volume ls | grep db_data         # the exact volume name
   docker compose down                     # no -v
   docker compose ps -a                    # must list nothing
   ```

2. Copy the datadir to a host path:

   ```bash
   mkdir -p /srv/eyened/db
   docker volume inspect <old-project>_db_data >/dev/null   # must succeed
   docker run --rm -v <old-project>_db_data:/from -v /srv/eyened/db:/to \
     --user 0:0 --entrypoint sh mysql:8.0.27 -c 'cp -a /from/. /to/ && chmod 750 /to'
   ```

3. In `deploy/.env`, set `DB_DATA_PATH=/srv/eyened/db`, and take these from the old
   `database/.env`: `MYSQL_ROOT_PASSWORD`; `MYSQL_USER` as `EYENED_DATABASE_USER`;
   `MYSQL_PASSWORD` as `EYENED_DATABASE_PASSWORD`; `MYSQL_DATABASE` as
   `EYENED_DATABASE_DATABASE`.
4. `docker compose up -d --build`. MySQL upgrades the datadir to 8.4, which 8.0 cannot open
   again, and `init` migrates the schema.
5. Sign in as an account from the old database and check your data. If `docker compose logs
   init` says `Empty database`, the copy did not land: stop, and recheck steps 2 and 3. Keep the
   old volume until this step passes.
