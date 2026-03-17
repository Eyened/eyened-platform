# Development Setup

**Prerequisites:** npm, python .venv with required packages, docker, docker compose  
**Working dir:** `dev` (cd dev)

## 0. Install Dependencies (first time only)
- Python deps:
  ```bash
  python -m pip install -r ../server/requirements.txt
  ```
- Client deps:
  ```bash
  (cd ../client && npm install)
  ```

## 1. Configure Settings and Secrets
- Copy `sample.env` to `.env` and fill out the required values.
- Ensure these are set:
  - `EYENED_API_SECRET_KEY` (JWT signing key)
  - `EYENED_DATABASE_*` (host, port, password; must match docker-compose)
  - `DEV_*` ports (nginx, server, client, adminer)
  - `EYENED_ROUTING_CONFIG=dev/nginx.conf`
- Update `nginx.conf` and `docker-compose.yml` volume paths with your storage roots.

## 2. Start Docker Services
- [Optional] You may want to update the name in docker-compose.yml
- Run:
  ```bash
  docker compose up -d
  ```
  This will start:
  - nginx fileserver that takes care of the routing (api, frontend and files)
  - start a database service
  - start an adminer service (for accessing the database through a browser)
  Notes:
  - `fileserver` uses `network_mode: host`, so `DEV_NGINX_PORT` is opened directly on the host.
  - Database root password is hard-coded to `test` in `dev/docker-compose.yml` (match `EYENED_DATABASE_PASSWORD`).

## 3. Populate the Database [Optional]
To copy over data (for example from a production environment), run this:
```bash
eorm load-dump -p path_to_dump
```
A dump can be created like this:
```bash
eorm save-dump -p path_to_dump
```

### Apply Pending Migrations (if needed)
Working from `orm/migrations`:
```
cd ../orm/migrations
```

Assuming the migration you want to run is found in `orm/migrations/alembic/versions`:

Run the migration:
```bash
alembic -x env_file=../../dev/.env upgrade head
```
You will be prompted to confirm the target database before the migration runs.

## 4. Start the Development Server & Client
Working from `dev` 
```
cd ../../dev
```

### Start the Server
- Run:
  ```bash
  ./start_server_dev.sh
  ```
  This will start the python FastAPI server

### Start the Client
- Run:
  ```bash
  ./start_client_dev.sh
  ```
  This will start the client in development mode, using vite hot-reload 