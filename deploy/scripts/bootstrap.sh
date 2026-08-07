#!/bin/sh
# First-run bootstrap: create the schema, seed form schemas, create an admin.
#
# Gated on database STATE, not on which stack is running: it acts only when
# this stack OWNS its database (local-db profile) and that database is EMPTY.
# It never migrates an existing database — the same .env can point at shared
# or production data, so drift is reported and left alone.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

# `-c orm/migrations/alembic.ini` from the container's WORKDIR (/app) does NOT
# work: that ini's `script_location = alembic` is resolved relative to the
# process's CWD, not to the ini file, so alembic looks for a nonexistent
# /app/alembic and fails with "Path doesn't exist: '/app/alembic'." on BOTH
# `current` and `heads` — identically, so an unguarded comparison of two
# equally-empty results would read as "schema is at head" instead of as the
# failure it is. `cd` into the migrations directory first, so alembic finds
# its default ./alembic.ini and script_location relative to it.
alembic_cmd() {
    compose exec -T server sh -c "cd orm/migrations && alembic $1" 2>/dev/null |
        tr -d '\r' | grep -v '^$' | tail -n 1
}

# --- 1. Does this stack own its database? ---------------------------------
case "$(env_get COMPOSE_PROFILES)" in
    *local-db*) ;;
    *)
        echo "bootstrap: this stack does not run the bundled database (no 'local-db'"
        echo "bootstrap: profile), so it cannot verify or safely initialise the"
        echo "bootstrap: database it points at. Nothing to do."
        exit 0
        ;;
esac

# --- 2. Wait for MySQL to report healthy -----------------------------------
cid=$(compose ps -q database || true)
[ -n "$cid" ] || die "bootstrap: the 'database' service is not running.
      Fix: start the stack first (./install.sh or make up)."

printf 'bootstrap: waiting for MySQL to become healthy'
status=unknown
i=0
while [ "$i" -lt 120 ]; do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo unknown)
    [ "$status" = healthy ] && break
    printf '.'
    sleep 2
    i=$((i + 1))
done
echo
[ "$status" = healthy ] || die "bootstrap: MySQL did not become healthy within 240s (last status: $status).
      Look at: $COMPOSE_BIN logs database"

# --- 3. Empty or populated? ------------------------------------------------
# A failed probe must never be mistaken for "populated": an empty string is
# not "0", so a naive test falls through to the else branch and reports
# "the database already has  tables" while quietly skipping initialisation.
# Anything that is not a plain number is an error.
require_count() {
    case "$1" in
        ''|*[!0-9]*) die "bootstrap: could not read $2 from the server container.
      Got: '$1'
      Look at: $COMPOSE_BIN logs server" ;;
    esac
}

tables=$(compose exec -T server python -c '
from sqlalchemy import inspect
from eyened_orm import Database
print(len(inspect(Database().engine).get_table_names()))
' | tr -d '\r' | tail -n 1)
require_count "$tables" "the table count"

if [ "$tables" = "0" ]; then
    echo "bootstrap: the database is empty — creating the schema and seeding form schemas."
    # The supported fresh-install path: create_all + stamp alembic at head, so
    # later upgrades apply only new migrations. NOT `alembic upgrade head`:
    # replaying the whole chain from zero is not a path this repo maintains.
    compose exec -T server eorm initialize-database --seed-form-schemas
else
    echo "bootstrap: the database already has $tables tables — it will not be migrated."
    current=$(alembic_cmd current)
    head=$(alembic_cmd heads)
    # `current` legitimately comes back empty (a schema with no alembic_version
    # row yet) — that is real drift, reported below, not a probe failure.
    # `head` reading the migration scripts on disk does not depend on the
    # database at all, so an empty `head` can only mean the alembic
    # invocation itself failed, and must not be compared away as "equal" to
    # an equally-empty `current`.
    [ -n "$head" ] || die "bootstrap: could not read the alembic head revision from the server container.
      Look at: $COMPOSE_BIN logs server"
    if [ "${current%% *}" = "${head%% *}" ]; then
        echo "bootstrap: schema is at head ($head). Nothing to do."
    else
        echo "bootstrap: WARNING — this database is not at the latest revision."
        echo "bootstrap:   current: ${current:-<none>}"
        echo "bootstrap:   head:    ${head:-<unknown>}"
        echo "bootstrap: Run 'make migrate' when you are sure this is the database"
        echo "bootstrap: you want to migrate. Nothing was changed."
    fi
fi

# --- 4. An admin account, once ---------------------------------------------
accounts=$(compose exec -T server python -c '
from sqlalchemy import func, select
from eyened_orm import Creator, Database
with Database().get_session() as session:
    print(session.execute(select(func.count()).select_from(Creator)).scalar_one())
' | tr -d '\r' | tail -n 1)
require_count "$accounts" "the account count"

if [ "$accounts" = "0" ]; then
    admin_password=$(gen_password)
    compose exec -T server eorm create-user \
        --username admin \
        --password "$admin_password" \
        --description "created by deploy/scripts/bootstrap.sh on first run"
    cat <<EOF

------------------------------------------------------------------------
An administrator account was created. This password is shown ONCE:

    username: admin
    password: $admin_password

Copy it now. More users can be created from the user interface.
------------------------------------------------------------------------
EOF
else
    echo "bootstrap: $accounts account(s) already exist — not creating an admin."
fi
