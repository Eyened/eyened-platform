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

The base stack runs without OIDC. To test the OIDC login flow, point the
`EYENED_OIDC_*` values in `.env` at a real provider.

The bundled local Keycloak is no longer available from this stack: it moved to
the unified `deploy/` stack, where it runs behind the `oidc` profile — see
[../deploy/keycloak/README.md](../deploy/keycloak/README.md). There is no
override to layer on here any more.

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
