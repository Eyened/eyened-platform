#!/bin/bash

alembic upgrade head --sql > ../docker_alembic/migration_output/migration.sql
echo "SQL for the migration generated: ../docker_alembic/migration_output/migration.sql"

