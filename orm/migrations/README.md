# Database Migration Guide

This guide outlines the process to:
- Set up a test database mirroring the source database
- Generate alembic migration
- Apply to test database

## Step 1: Create Test Database

1. Set the environment variables in `.env`:
   ```env
   TEST_DB_PORT=    # Access port for the test database (e.g. 3307)
   PHPMYADMIN_PORT= # Access port for the phpmyadmin (e.g. 8080)
   MYSQL_ROOT_PASSWORD= # Something random
   ```

2. Create a new database in a docker environment:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

## Step 2: Set Up Environments for Data Transfer

Create two environment files in `orm/eyened_orm/environments/`:

1. Source environment (`source.env`):
   ```env
   DB_HOST=      # Host on which current database is running
   DB_PORT=      # Port on which to access the db
   DB_USER=      # User with 'mysqldump' and 'SELECT' permissions
   DB_PASSWORD=  # Password for user
   DB_NAME=eyened_database
   ```

2. Test environment (`test.env`):
   ```env
   DB_HOST=      # Host on which you are running the test database
   DB_PORT=      # Equal to TEST_DB_PORT
   DB_USER=root
   DB_PASSWORD=  # MYSQL_ROOT_PASSWORD
   DB_NAME=eyened_database
   ```

## Step 3: Transfer Data from Source to Test

Populate the test database with some data to make a meaningful testing environment:

```bash
eorm test -s source -t test -r root_conditions.json
```

In `root_conditions.json` you can specify which data to transfer from source to test. Foreign keys are followed in both directions to expand the context. For example, inserting a single Patient will also resolve the Project, Studies, Series, ImageInstances, Annotations etc. associated with that patient.

## Step 4: Configure Alembic Connection

Set up alembic to interact with the test database:
```bash
eorm set-connection-string -e test
```
This command sets the `sqlalchemy.url` in `alembic.ini` based on the variables in `test.env`.

## Step 5: Generate Migration

Generate the migration using:
```bash
alembic revision --autogenerate -m "test"
```

If necessary, update the `upgrade` and `downgrade` methods in the generated python file in `alembic/versions`

## Step 6: Apply migration

```bash
alembic upgrade head
```

This will sync the orm and database.

## Step 7: Testing

Depending on the nature of the changes, test the following on the new database layout:
- Connect a viewer
- Test eorm CLI
- Test image importing

