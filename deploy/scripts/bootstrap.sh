#!/bin/sh
# First-run bootstrap: create the schema, seed form schemas, create an admin.
#
# Gated on database STATE, not on which stack is running: it acts only when
# this stack OWNS its database (local-db profile, EYENED_DATABASE_HOST still
# pointed at the bundled 'database' service) and that database is EMPTY.
# It never migrates an existing database — the same .env can point at shared
# or production data, so drift is reported and left alone.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

# --- 0. Can ownership even be determined? -----------------------------------
# env_get silently returns empty for a KEY that is absent from .env AND for a
# .env that does not exist at all — the two are not the same thing. Without
# .env, COMPOSE_PROFILES read from the file is always empty, so an unguarded
# gate below would print "does not run the bundled database" even while a
# COMPOSE_PROFILES exported in the shell has compose actually running
# 'local-db' against it. Refuse to guess instead.
[ -f "$DEPLOY_DIR/.env" ] || die "bootstrap: $DEPLOY_DIR/.env does not exist, so bootstrap cannot tell
      whether this stack owns its database.
      Fix: run ./install.sh or 'make up' first — both create deploy/.env before
      calling this script."

# A real exported COMPOSE_PROFILES / EYENED_DATABASE_HOST takes precedence
# over deploy/.env, because that is also how the compose CLI resolves them
# (shell environment overrides the project .env file). Reading only the file
# here would disagree with what the running stack is actually doing whenever
# either variable is supplied on the invoking shell rather than in .env.
profiles=${COMPOSE_PROFILES:-$(env_get COMPOSE_PROFILES)}
db_host=${EYENED_DATABASE_HOST:-$(env_get EYENED_DATABASE_HOST)}

# `alembic $1` output, exit status included: a pipeline like
# `compose exec ... | tr -d '\r' | tail -n 1` (used for the table/account
# probes below) keeps only the LAST stage's exit status, so a failed `compose
# exec` disappears and the pipeline reports success with whatever partial
# text made it to stdout. alembic makes that worse than a merely empty
# result: a command-level failure (e.g. a script_location that does not
# resolve from the container's CWD — this repo's actual alembic.ini, see the
# commit this function was added in) is printed as "FAILED: ..." on STDOUT,
# not stderr, so it is neither empty nor numeric-shaped by accident, and a
# check that only guards against emptiness never fires on it.
alembic_cmd() {
    # The assignment is wrapped in its own if/else, not left as a plain
    # statement, because under `set -e` a plain `_out=$(cmd)` whose `cmd`
    # fails aborts THIS subshell immediately — before the `printf` below
    # ever runs — so the caller's capture comes back empty even though the
    # exit status still (correctly) propagates as non-zero. That silently
    # threw away the exact diagnostic text this function exists to preserve
    # (found live: `die` printed "Output:" with nothing after it, while a
    # bare `sh -c` reproduction of the same failure showed the text fine).
    if _out=$(compose exec -T server sh -c "cd orm/migrations && alembic $1" 2>&1); then
        _rc=0
    else
        _rc=$?
    fi
    printf '%s\n' "$_out" | tr -d '\r'
    return $_rc
}

# `alembic heads` reads migration scripts off disk — it does not touch the
# database at all, so it has no legitimate reason to come back empty or
# non-numeric. Both the exit status AND the shape of the result are checked:
# the exit status catches most failures (including the FAILED-on-stdout one
# above), and the shape check is what still catches a success (rc=0) that
# nonetheless returns something that is not a revision id.
alembic_head() {
    if ! _out=$(alembic_cmd "$1"); then
        die "bootstrap: 'alembic $1' failed inside the server container.
      Output:
$(printf '%s' "$_out" | sed 's/^/      /')"
    fi
    _rev=$(printf '%s\n' "$_out" | grep -v '^$' | grep -vi '^INFO' | tail -n 1)
    case "${_rev%% *}" in
        ''|*[!0-9a-f]*)
            die "bootstrap: 'alembic $1' did not return a revision id inside the server container.
      Output:
$(printf '%s' "$_out" | sed 's/^/      /')" ;;
    esac
    printf '%s' "$_rev"
}

# `alembic current` is different: a database with tables but no
# alembic_version row legitimately prints nothing and exits 0 — that is real
# state (see section 3's "broken init" branch below), not a probe failure.
# Only a non-zero exit status means the invocation itself failed.
alembic_current() {
    if ! _out=$(alembic_cmd current); then
        die "bootstrap: 'alembic current' failed inside the server container.
      Output:
$(printf '%s' "$_out" | sed 's/^/      /')"
    fi
    printf '%s\n' "$_out" | grep -v '^$' | grep -vi '^INFO' | tail -n 1
}

# --- 1. Does this stack own its database? ---------------------------------
# Comma-wrapped exact-segment match: a bare substring test (`*local-db*`)
# also matches 'no-local-db' or 'local-db-external'.
case ",$profiles," in
    *,local-db,*) ;;
    *)
        echo "bootstrap: this stack does not run the bundled database (no 'local-db'"
        echo "bootstrap: profile), so it cannot verify or safely initialise the"
        echo "bootstrap: database it points at. Nothing to do."
        exit 0
        ;;
esac

# The profile is only half of "owns its database": every query below targets
# EYENED_DATABASE_HOST, and the documented external-database migration
# (.env.example) is two independent edits — drop 'local-db' from
# COMPOSE_PROFILES, then repoint EYENED_DATABASE_*. Doing only the second
# leaves 'local-db' in place while every read and write in this script goes
# to the external host instead of the bundled container.
case "$db_host" in
    ''|database) ;;
    *)
        die "bootstrap: COMPOSE_PROFILES has 'local-db' but EYENED_DATABASE_HOST is
      '$db_host', not the bundled 'database' service.
      This looks like a half-completed move to an external database — refusing
      to guess which one bootstrap should touch.
      Fix: either remove 'local-db' from COMPOSE_PROFILES (bootstrap will then
      decline this database outright) or point EYENED_DATABASE_HOST back at
      'database' (the bundled one)." ;;
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

# Whether it is safe to look for/create an admin below: only once the schema
# is verified to be in a KNOWN-GOOD state this run — a fresh initialisation,
# or an existing database already confirmed at head. Drift and "broken init"
# are explicitly NOT known-good: writing a Creator row into either would
# contradict the "Nothing was changed" / "cannot repair" message this
# section just printed.
schema_ok=0

if [ "$tables" = "0" ]; then
    echo "bootstrap: the database is empty — creating the schema and seeding form schemas."
    # The supported fresh-install path: create_all + stamp alembic at head, so
    # later upgrades apply only new migrations. NOT `alembic upgrade head`:
    # replaying the whole chain from zero is not a path this repo maintains.
    # A failure here aborts the script under `set -e` before schema_ok is set,
    # so a partial failure this run never falls through to admin creation.
    compose exec -T server eorm initialize-database --seed-form-schemas
    schema_ok=1
else
    echo "bootstrap: the database already has $tables tables — it will not be migrated."
    current=$(alembic_current)
    head=$(alembic_head heads)
    if [ -z "$current" ]; then
        # Tables exist but alembic was never stamped: create_all succeeded
        # and something after it (stamping, or --seed-form-schemas) did not.
        # This is a broken initialisation, not drift, and 'make migrate'
        # cannot repair a schema that was never fully created — telling the
        # operator to run it would misdiagnose the problem.
        echo "bootstrap: WARNING — this database has tables but no alembic_version row."
        echo "bootstrap: A previous initialisation likely did not finish (schema creation"
        echo "bootstrap: succeeded; stamping or form-schema seeding did not). This is not"
        echo "bootstrap: something bootstrap can repair automatically — inspect the"
        echo "bootstrap: database directly before proceeding."
    elif [ "${current%% *}" = "${head%% *}" ]; then
        echo "bootstrap: schema is at head ($head). Nothing to do."
        schema_ok=1
    else
        echo "bootstrap: WARNING — this database is not at the latest revision."
        echo "bootstrap:   current: $current"
        echo "bootstrap:   head:    $head"
        echo "bootstrap: Run 'make migrate' when you are sure this is the database"
        echo "bootstrap: you want to migrate. Nothing was changed."
    fi
fi

# --- 4. An admin account, once ---------------------------------------------
if [ "$schema_ok" != "1" ]; then
    echo "bootstrap: skipping the admin-account check — the schema above is not in a"
    echo "bootstrap: known-good state."
else
    accounts=$(compose exec -T server python -c '
from sqlalchemy import func, select
from eyened_orm import Creator, Database
with Database().get_session() as session:
    print(session.execute(select(func.count()).select_from(Creator)).scalar_one())
' | tr -d '\r' | tail -n 1)
    require_count "$accounts" "the account count"

    if [ "$accounts" = "0" ]; then
        admin_password=$(gen_password)
        # The password goes in over stdin, not `--password` on the command
        # line: an argv value is visible to any other user on this host who
        # runs `ps` for the life of the exec. `create-user`'s --password is a
        # click option with prompt=True and confirmation_prompt=True, so
        # omitting the flag makes it prompt twice on stdin instead.
        pw_file=$(mktemp) || die "bootstrap: could not create a temp file for the admin password."
        trap 'rm -f "$pw_file"' EXIT
        # A signal is not an exit: whether EXIT also runs on SIGINT/SIGTERM is
        # shell-dependent, and where it does not, Ctrl-C during the exec below
        # leaves this file — holding the plaintext admin password — behind in
        # /tmp. Handling both signals explicitly removes it in every shell; the
        # `exit` then re-runs the EXIT trap, which is harmless (`rm -f`).
        trap 'rm -f "$pw_file"; exit 130' INT
        trap 'rm -f "$pw_file"; exit 143' TERM
        printf '%s\n%s\n' "$admin_password" "$admin_password" > "$pw_file"
        compose exec -T server eorm create-user \
            --username admin \
            --description "created by deploy/scripts/bootstrap.sh on first run" \
            < "$pw_file"
        rm -f "$pw_file"
        trap - EXIT INT TERM
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
fi
