#!/bin/bash

echo "Setting connection string for test environment..."
eorm set_connection_string -e test

echo "Creating tables and inserting test_data..."
eorm test -s source -t test -r root_conditions.json

echo "Running migration and output to SQL..."

# Define output path
output_dir="sql"
mkdir -p "$output_dir"  # Ensure directory exists

# Get the current revision from the database
current_rev=$(alembic current | grep -oE '[a-f0-9]{12}')

# Get the latest head revision
head_rev=$(alembic heads | grep -oE '[a-f0-9]{12}')

# Generate SQL for migrations between the current revision and head
if [ "$current_rev" != "$head_rev" ]; then
    alembic upgrade "$current_rev:$head_rev" --sql > "$output_dir/migration_latest.sql"
    echo "SQL for the latest migration generated: $output_dir/migration_latest.sql"
else
    echo "No new migrations to apply."
fi

# Actually apply the migration
alembic upgrade head

# Keep container running for debugging
tail -f /dev/null
