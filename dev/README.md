# Development Setup

**Prerequisites:** npm, python .venv with required packages, docker, docker compose  
**Working dir:** `dev` (cd dev)

## 1. Configure Environment Variables
- Copy `sample.env` to `.env` and fill out the required values.

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

## 3. Populate the Database [Optional]
To copy over some data (for example from a production environment), run this:
```bash
eorm database-mirror-test -c transfer-config.yml
```

where `transfer-config.yml` has the following structure:
```yaml
source:
  host: 
  port: 
  user: 
  password: 
  database: eyened_database

target:
  host: 
  port: 
  user: root
  password: test
  database: eyened_database

copy_objects:
  - table: Patient
    clause:
      PatientIdentifier: '1'
  - table: Patient
    clause:
      PatientIdentifier: '2'
```

**Note:** The `source` is the source database (e.g. production), `target` is the development database (use `port=DATABASE_PORT` from the `.env`, user `root` and password `test` are hardcoded currently).

### Apply Pending Migrations (if needed)
Working from `orm/migrations` (`cd ../orm/migrations`):

Assuming the migration you want to run is found in `orm/migrations/alembic/versions`:

1. Set the connection string in `orm/migrations/alembic.ini` by running:
   ```bash
   python set_connection_string.py ../../dev/.env
   ```

2. Double check if the connection string is correct:
   ```bash
   cat alembic.ini | grep url
   ```

3. Run the migration:
   ```bash
   alembic upgrade head
   ```

## 4. Start the Development Server & Client
Working from `dev` (`cd ../../dev`):

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

