#!/bin/bash

# Prevously: -P"3306"
while ! mysqladmin ping -h test-database -P 3306 --silent; do
    echo "Waiting for database connection..."
    sleep 1
done

# Insert test_data
eorm test

# Set connection string for alembic
cp /app/docker/alembic.ini /app/alembic_/alembic.ini
python3 /app/docker/set_connection_string.py


# Run Alembic migration and generate migration.sql, migration_lates.sql if ALEMBIC_AUTO_MIGRATION is true
if [ "$ALEMBIC_AUTO_MIGRATION" = "true" ]; then
    mkdir -p /app/migration_output


    echo "Running migration and output to migration.sql..."
    # Get the current revision from the database
    current_rev=$(alembic current | grep -oE '[a-f0-9]{12}')
    # Get the latest head revision
    head_rev=$(alembic heads | grep -oE '[a-f0-9]{12}')

    # Generate SQL for migrations between the current revision and head
    if [ "$current_rev" != "$head_rev" ]; then
        alembic upgrade $current_rev:$head_rev --sql > /app/migration_output/migration_latest.sql
        echo "SQL for the latest migration generated: ../docker/migration_output/migration_latest.sql"
    else
        echo "No new migrations to apply."
    fi
    alembic upgrade head

else
    echo "Skipping Alembic migration."
fi


# Keep container running for debugging
tail -f /dev/null




