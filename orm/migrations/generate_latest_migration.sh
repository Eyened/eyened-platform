#!/bin/bash

# Get the current revision from the database
current_rev=$(alembic current | grep -oE '[a-f0-9]{12}')
# Get the latest head revision
head_rev=$(alembic heads | grep -oE '[a-f0-9]{12}')

# Generate SQL for migrations between the current revision and head
if [ "$current_rev" != "$head_rev" ]; then
  alembic upgrade $current_rev:$head_rev --sql > sql/latest_migration.sql
  echo "SQL for the latest migration generated: sql/latest_migration.sql"
else
  echo "No new migrations to apply."
fi
