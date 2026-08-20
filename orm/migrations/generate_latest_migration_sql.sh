#!/bin/bash

# Get the current revision from the database. Revision ids are not
# necessarily hex (e.g. the squashed baseline is "orm_baseline"), and
# `alembic current` can trail extra text such as "(head)", so just take
# the first word of the first line rather than pattern-matching the id.
current_rev=$(alembic current | awk '{print $1; exit}')
# Get the latest head revision
head_rev=$(alembic heads | awk '{print $1; exit}')

if [ -z "$current_rev" ]; then
  echo "Error: could not determine the current revision (is the target database reachable and stamped?)." >&2
  exit 1
fi

# Generate SQL for migrations between the current revision and head
if [ "$current_rev" != "$head_rev" ]; then
  tmp_sql=$(mktemp)
  if echo 'y' | alembic upgrade "$current_rev:$head_rev" --sql > "$tmp_sql"; then
    mv "$tmp_sql" sql/latest_migration.sql
    echo "SQL for the latest migration generated: sql/latest_migration.sql"
  else
    status=$?
    rm -f "$tmp_sql"
    echo "Error: alembic upgrade --sql failed (exit $status); sql/latest_migration.sql left unchanged." >&2
    exit 1
  fi
else
  echo "No new migrations to apply."
fi
