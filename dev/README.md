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

## 2. Start Docker Services
- The database is a separate stack and is not part of this compose file. Start it first (see [../database/README.md](../database/README.md)); the server reaches it via `host.docker.internal` using the `EYENED_DATABASE_*` values in `.env`.
- [Optional] You may want to update the name in docker-compose.yml
- Run:
  ```bash
  docker compose up -d
  ```
  This will start:
  - nginx fileserver that takes care of the routing (api, frontend and files)
  - redis
  - the server and client

### OIDC login (optional)

The base stack runs without OIDC. To test the OIDC login flow, either point the
`EYENED_OIDC_*` values in `.env` at a real provider, or spin up the bundled local
Keycloak — see [keycloak/README.md](./keycloak/README.md).

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

If you populated the database from a dump in step 3, the dump's `alembic_version` table came with it. A dump already at the legacy head (`b2e2800000b2`) should be stamped, not upgraded — run `alembic -x env_file=../../dev/.env stamp orm_baseline` instead. An older dump follows `docs/runbooks/2026-08-20-alembic-squash-cutover.md`.

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
  This will start the client in development mode, using vite hot-reload.

## Run unit tests

First time only: install testing dependencies. `test-requirements.txt` chains the
server runtime deps and pins pytest; the editable `orm` install is what makes
`eyened_orm` importable at test-collection time.

```shell
pip install -e ../orm
pip install -r ../server/test-requirements.txt
```

Then run `pytest` from the root folder:

```shell
pytest
# or, when in ./dev:
pytest ..
```
