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
  # Temp file lives next to the destination, not $TMPDIR: that keeps the
  # final mv a same-filesystem rename (atomic, all-or-nothing) instead of a
  # cross-filesystem copy+unlink.
  tmp_sql=$(mktemp sql/.latest_migration.sql.XXXXXX)
  if echo 'y' | alembic upgrade "$current_rev:$head_rev" --sql > "$tmp_sql"; then
    # mktemp creates the file mode 600; restore the tracked file's usual
    # mode before the rename, so a regeneration doesn't leave it owner-only.
    chmod 644 "$tmp_sql"
    if mv "$tmp_sql" sql/latest_migration.sql; then
      echo "SQL for the latest migration generated: sql/latest_migration.sql"
    else
      status=$?
      rm -f "$tmp_sql"
      echo "Error: mv failed (exit $status); sql/latest_migration.sql left unchanged." >&2
      exit 1
    fi
  else
    status=$?
    rm -f "$tmp_sql"
    echo "Error: alembic upgrade --sql failed (exit $status); sql/latest_migration.sql left unchanged." >&2
    exit 1
  fi
else
  echo "No new migrations to apply."
fi
