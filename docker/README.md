## EyeNED Docker Setup

Production stack: `server` (API), `client` (UI), `fileserver` (nginx reverse proxy + file serving).

Prerequisite: a MySQL database. See the [database](../database/) folder to start one locally.

### 1) Configure before first run

Copy `.env.example` to `.env` and set database credentials, Redis password, and `PORT`.

Set `EYENED_STORAGE_ROOT` to a writable host directory (default `/storage`). Compose mounts this path into the server; thumbnails are served from `{EYENED_STORAGE_ROOT}/thumbnails`.

Edit `nginx.conf`:
- Add one `location /<StorageBackend.Key>/ { ... }` block per mounted dataset path.
- Keep `alias` paths matching the container mount paths from `docker-compose.yaml`.

Add read-only dataset mounts under `fileserver.volumes` in `docker-compose.yaml` when needed.

### 2) Build and start the platform

```bash
docker compose up -d --build
```

### 3) Initialize app

Run once after services are up:

```bash
docker compose exec -it server bash
```

Initialize database (runs the Alembic migration trail to head):

```bash
eorm initialize-database
eorm seed-form-schemas
```

Create a user (for log in to front-end and/or use with api-client):

```bash
eorm create-user
```
