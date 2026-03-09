## EyeNED Docker Setup

Production stack: `server` (API), `client` (UI), `fileserver` (nginx reverse proxy + file serving).

### 1) Configure before first run

Edit `docker-compose.yaml`:
- `server.volumes`: replace `</path/to/segmentations.zarr>` with a writable host path.
- `fileserver.volumes`: replace `</path/to/thumbnails>` with your thumbnails path.
- `fileserver.volumes`: replace/add dataset mounts (for example `</mnt/data_source_1>`).

Edit `nginx.conf`:
- Add one `location /<StorageBackend.Key>/ { ... }` block per mounted dataset path.
- Keep `alias` paths matching the container mount paths from `docker-compose.yaml`.

Create or update `.env`:
```env
PORT=<port to expose the app>
EYENED_API_SECRET_KEY=<a random string>
EYENED_DATABASE_USER=<db-user>
EYENED_DATABASE_PASSWORD=<db-password>
EYENED_DATABASE_HOST=<db-host, use host.docker.internal for localhost>
EYENED_DATABASE_PORT=<db-port>
```

### 2) Build and start

```bash
docker compose build
docker compose up -d
docker compose logs -f
```

### 3) Initialize app

Run once after services are up:

Enter terminal inside the server container:
```bash
docker compose exec server bash
```

Initialize database
```bash
eorm initialize-database
```

Create user (for log in to front-end and/or api-client)
```bash
eorm create-user
```