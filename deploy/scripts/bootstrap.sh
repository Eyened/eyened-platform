#!/bin/sh
# First-run bootstrap: create the schema, seed form schemas, and put this
# stack under an active administrator — creating one on a genuinely empty
# database, or refusing loudly and naming the fix when accounts already exist
# but none of them administers anything. Never promotes an existing account
# on its own; see section 4.
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
      Fix: run './eyened install' or './eyened up' first — both create deploy/.env
      before calling this script."

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
      Fix: start the stack first ('./eyened install' or './eyened up')."

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
      The probe's own error output, if it produced any, is printed ABOVE this
      message — not in the container log. This runs as a one-off
      '$COMPOSE_BIN exec', whose stderr goes straight to this terminal, while
      '$COMPOSE_BIN logs server' carries gunicorn's output and never sees it.
      If nothing was printed above, the exec did not run at all: check that
      the server container is up ('$COMPOSE_BIN ps')." ;;
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
    # The supported fresh-install path. `initialize-database` runs the alembic
    # trail to head; since the squash there is no separate table-creation step,
    # because orm_baseline — the root migration — creates the whole schema
    # itself. So this is not "replaying years of history from zero"; it is one
    # migration plus whatever has landed after it.
    # A failure here aborts the script under `set -e` before schema_ok is set,
    # so a partial failure this run never falls through to admin creation.
    compose exec -T server eorm initialize-database --seed-form-schemas
    schema_ok=1
else
    echo "bootstrap: the database already has $tables tables — it will not be migrated."
    current=$(alembic_current)
    head=$(alembic_head heads)
    if [ -z "$current" ]; then
        # Tables exist but no alembic_version row. initialize-database runs the
        # migration trail, and alembic writes that row as it applies, so this is
        # no longer "create_all succeeded and stamping did not" — that sequence
        # no longer exists. What remains are a schema restored from a logical
        # dump that did not carry its alembic_version table, a schema created by
        # a release older than the migration squash, or a run that died partway
        # (MySQL DDL is not transactional, so a half-applied migration leaves
        # tables behind). Which revision such a schema should be stamped at
        # depends on what it actually contains, so bootstrap reports and stops
        # rather than guessing — applying migrations blind would misdiagnose all
        # three.
        echo "bootstrap: WARNING — this database has tables but no alembic_version row."
        echo "bootstrap: That is usually a schema restored from a logical dump that did not"
        echo "bootstrap: include the alembic_version table, or one created by a release older"
        echo "bootstrap: than the migration squash. Which revision it should be stamped at"
        echo "bootstrap: depends on what the schema actually is, so bootstrap will not guess —"
        echo "bootstrap: inspect the database directly before proceeding."
    elif [ "${current%% *}" = "${head%% *}" ]; then
        echo "bootstrap: schema is at head ($head). Nothing to do."
        schema_ok=1
    else
        echo "bootstrap: WARNING — this database is not at the latest revision."
        echo "bootstrap:   current: $current"
        echo "bootstrap:   head:    $head"
        echo "bootstrap: Run './eyened migrate' when you are sure this is the database"
        echo "bootstrap: you want to migrate. Nothing was changed."
    fi
fi

# --- 4. An administrator, once ----------------------------------------------
# Three states, not two: RBAC enforcement means the account count alone no
# longer says whether this stack can be administered — Creator.IsAdmin
# defaults to false (orm/eyened_orm/creator.py), so an account existing is
# not the same as an administrator existing.
if [ "$schema_ok" != "1" ]; then
    echo "bootstrap: skipping the administrator check — the schema above is not in a"
    echo "bootstrap: known-good state."
else
    # Shell environment overrides deploy/.env, the same precedence compose
    # itself resolves EYENED_API_ADMIN_USERNAME with when it interpolates the
    # server service (see step 0 above for COMPOSE_PROFILES/EYENED_DATABASE_HOST,
    # the same trap) — so the account bootstrap creates and the account the
    # dev-auth bypass resolves (server/services/current_user.py) cannot
    # disagree just because one of them read .env and the other read the
    # calling shell.
    admin_username=${EYENED_API_ADMIN_USERNAME:-$(env_get EYENED_API_ADMIN_USERNAME)}
    admin_username=${admin_username:-admin}

    accounts=$(compose exec -T server python -c '
from sqlalchemy import func, select
from eyened_orm import Creator, Database
with Database().get_session() as session:
    print(session.execute(select(func.count()).select_from(Creator)).scalar_one())
' | tr -d '\r' | tail -n 1)
    require_count "$accounts" "the account count"

    # count_admins() is imported rather than re-spelled here so the "active
    # administrator" definition can never drift from the one
    # orm/eyened_orm/authz/bootstrap.py itself uses for the last-admin guard.
    admins=$(compose exec -T server python -c '
from eyened_orm import Database
from eyened_orm.authz.bootstrap import count_admins
with Database().get_session() as session:
    print(count_admins(session))
' | tr -d '\r' | tail -n 1)
    require_count "$admins" "the active-administrator count"

    if [ "$accounts" = "0" ]; then
        admin_password=$(gen_hex 12)
        # The password goes in over stdin, not `--password` on the command
        # line: an argv value is visible to any other user on this host who
        # runs `ps` for the life of the exec. `init-admin`'s --password is a
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
        outcome=$(compose exec -T server eorm init-admin \
            --username "$admin_username" \
            < "$pw_file" | tr -d '\r' | tail -n 1)
        rm -f "$pw_file"
        trap - EXIT INT TERM
        # init-admin reports its own outcome (created, promoted, unchanged,
        # ...). Only 'created' confirms this branch's premise (0 accounts)
        # still held when the command ran, so only 'created' may claim an
        # account was made or print a password — see orm/eyened_orm/commands/rbac.py.
        case "$outcome" in
            "$admin_username: created")
                cat <<EOF

------------------------------------------------------------------------
An administrator account was created. This password is shown ONCE:

    username: $admin_username
    password: $admin_password

Copy it now. More users can be created from the user interface.
------------------------------------------------------------------------
EOF
                ;;
            *)
                die "bootstrap: 'eorm init-admin' did not report creating '$admin_username'.
      Got: '$outcome'
      No password was printed. Inspect the account by hand before assuming
      one exists — run:
          cd deploy && $COMPOSE_BIN exec server eorm init-admin --username $admin_username" ;;
        esac
    elif [ "$admins" = "0" ]; then
        # Refuse loudly, never promote. ensure_admin() resets an existing
        # account's password whenever a supplied password does not already
        # verify (orm/eyened_orm/authz/bootstrap.py) — handing this run's
        # freshly generated password to an existing '$admin_username' account
        # would silently change that account's password. Only an operator who
        # deliberately means to do that should run init-admin themselves.
        die "bootstrap: $accounts account(s) already exist and NONE of them is an
      active administrator. Nobody can administer this stack, and bootstrap
      will not promote an existing account automatically.
      Fix: run
          cd deploy && $COMPOSE_BIN exec server eorm init-admin --username $admin_username
      (docker-compose in place of docker compose if that is what this host
      has — see deploy/README.md) and follow its prompts."
    else
        echo "bootstrap: $accounts account(s) exist, $admins of them an active administrator — nothing to do."
    fi
fi
