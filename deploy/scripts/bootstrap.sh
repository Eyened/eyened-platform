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

    # alembic_current() dies (see above) the moment alembic_version holds a
    # revision id it cannot resolve — before any branch below ever runs. A
    # database restored from a pre-squash dump is exactly that: it carries
    # alembic_version, but the squash moved every legacy id off alembic's
    # search path (orm/migrations/alembic/versions_archive/ holds all 24 of
    # them), so it is the VALUE that fails to resolve, not the invocation.
    #
    # Reading that row directly first — the same probe shape section 4 uses
    # — is what separates the two, without an allow-list of ids. A row this
    # probe could READ proves the container is up, the credentials work and
    # the database is reachable — but NOT that an 'alembic current' which
    # then fails is failing on the VALUE: it needs more than the probe does
    # (see below), so alembic's own text is what settles that. A row it
    # could NOT read (no table, or the exec itself failed) leaves
    # version_num empty, and the condition below falls through to
    # alembic_current() unchanged — so a genuine failure (wrong password,
    # container down, unrelated error) still dies loudly with the raw
    # output. This is a narrow, additional check, not a replacement for that
    # die.
    #
    # fetchone() is exact rather than arbitrary here: alembic_version holds
    # one row per head, and this branch's chain is linear with a single leaf
    # (orm/eyened_orm/tests/test_migration_chain.py enforces that), so a
    # second row cannot exist.
    version_num=$(compose exec -T server python -c '
from sqlalchemy import inspect, text
from eyened_orm import Database
engine = Database().engine
if inspect(engine).has_table("alembic_version"):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    print(row[0] if row else "")
else:
    print("")
' | tr -d '\r' | tail -n 1)

    # A revision id is a bare token. Docker, compose and Python write their
    # own failures to stderr, which goes straight to this terminal and never
    # into this capture, so anything carrying spaces or punctuation did not
    # come out of the version row: treat it as unread rather than as an id,
    # and say so — that unlabelled text immediately above is its explanation,
    # the same convention require_count's die spells out.
    case "$version_num" in
        *[!0-9A-Za-z_]*)
            echo "bootstrap: the alembic_version probe returned no revision id — its own error"
            echo "bootstrap: output, if it produced any, is the text printed ABOVE this line."
            version_num='' ;;
    esac

    # The probe and 'alembic current' do not depend on the same things: the
    # probe is a direct query, while 'alembic current' additionally needs
    # orm/migrations to exist in the container and the whole revision map on
    # disk to BUILD. The dev stack bind-mounts ../orm into the container, so
    # a half-written migration in this working tree breaks that map while
    # the version row still reads perfectly — and a database sitting at
    # orm_baseline would then be reported as a pre-squash dump. Alembic says
    # which of the two it is, so capture its output rather than discarding
    # it, and only read "pre-squash dump" out of a failure that names an id
    # alembic could not place.
    #
    # Costs one extra 'alembic current' on a healthy populated database.
    # That is the price of leaving alembic_current()'s die untouched: the
    # alternative is inlining its failure handling here, i.e. two copies
    # of the loud path to keep in step instead of one.
    alembic_current_state=ok
    if [ -n "$version_num" ] && ! alembic_current_out=$(alembic_cmd current 2>&1); then
        case "$alembic_current_out" in
            *"Can't locate revision"*) alembic_current_state=unresolvable ;;
            *)                         alembic_current_state=failed ;;
        esac
    fi

    if [ "$alembic_current_state" = unresolvable ]; then
        echo "bootstrap: WARNING — this database's alembic_version table holds"
        echo "bootstrap: $version_num, which 'alembic current' cannot resolve. The read above"
        echo "bootstrap: succeeded, so the container and the database are reachable — it is the"
        echo "bootstrap: VALUE alembic cannot place. That is what a database restored from a"
        echo "bootstrap: pre-squash dump looks like: the squash moved every legacy revision id"
        echo "bootstrap: off alembic's search path (orm/migrations/alembic/versions_archive/)."
        if [ "$version_num" = "b2e2800000b2" ]; then
            # The same state the squash cutover runbook's step 2 checks for,
            # reached through a different door — a dump restored later,
            # rather than a live site walked through the cutover. Its
            # recovery is one command: stamp at the new root rather than
            # trying to resolve an id the squash removed from the map.
            # Bootstrap does not run it itself — same "reports and stops"
            # contract as the two branches below.
            echo "bootstrap: That is the legacy head, so the recovery is a stamp rather than an"
            echo "bootstrap: upgrade (--purge skips resolving the legacy id), then a run to head:"
            echo "bootstrap:   cd deploy && $COMPOSE_BIN exec -it server sh -c 'cd orm/migrations && alembic stamp --purge orm_baseline'"
            echo "bootstrap:   $COMPOSE_BIN exec -it server sh -c 'cd orm/migrations && alembic upgrade head'"
            echo "bootstrap: Run both, in that order, from the repository root: the second line is"
            echo "bootstrap: what './eyened migrate' runs, from the deploy/ the first leaves you in."
        else
            # Not the legacy head. The squash left no down_revision path from
            # any earlier id to orm_baseline, so such a dump cannot be
            # stamped where it stands — it has to be walked forward on a
            # pre-squash checkout first, which is a procedure, not a command
            # bootstrap can print. The message does not assert the id is
            # older: an id this checkout's map simply does not contain is
            # also unresolvable, and the runbook's rule for anything that
            # does not match it is to stop and escalate.
            echo "bootstrap: That is not the legacy head (b2e2800000b2), so there is no"
            echo "bootstrap: one-command recovery — a dump from further back must be walked"
            echo "bootstrap: forward on a pre-squash checkout first. Follow"
            echo "bootstrap: docs/runbooks/2026-08-20-alembic-squash-cutover.md."
        fi
        echo "bootstrap: Nothing was changed. The stack itself still comes up, but this"
        echo "bootstrap: database is not usable by it until the above is done."
    elif [ "$alembic_current_state" = failed ]; then
        echo "bootstrap: WARNING — 'alembic current' failed inside the server container, and"
        echo "bootstrap: not on a revision id it could not place, so bootstrap cannot say what"
        echo "bootstrap: this database is. The version row itself reads fine ($version_num)."
        echo "bootstrap: A revision map that does not build is the reachable cause: the dev"
        echo "bootstrap: stack mounts this working tree's orm/ into the container, so an"
        echo "bootstrap: unfinished migration in it breaks the map. Alembic said:"
        printf '%s\n' "$alembic_current_out" | sed 's/^/bootstrap:   /'
        echo "bootstrap: Fix that first, then re-run. Nothing was changed."
    else
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
fi

# --- 4. An administrator, once ----------------------------------------------
# Four states, not two: RBAC enforcement means the account count alone no
# longer says whether this stack can be administered — Creator.IsAdmin
# defaults to false (orm/eyened_orm/creator.py), so an account existing is
# not the same as an administrator existing, and an administrator existing is
# not the same as an ACTIVE one.
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
    # The second number counts IsAdmin rows whatever their Inactive flag: that
    # is what separates "no administrator exists" from "the only administrator
    # is deactivated" below, two states that need two different commands. One
    # round-trip for both, so they cannot describe two different moments.
    admin_counts=$(compose exec -T server python -c '
from sqlalchemy import func, select
from eyened_orm import Creator, Database
from eyened_orm.authz.bootstrap import count_admins
with Database().get_session() as session:
    print(count_admins(session), session.execute(
        select(func.count()).select_from(Creator).where(Creator.IsAdmin.is_(True))
    ).scalar_one())
' | tr -d '\r' | tail -n 1)
    # `read`, not two ${..%% *}/${..#* } strips: if the probe ever prints only
    # one number, those would silently hand back the SAME number twice and the
    # deactivated state would be misread as "no administrator". read leaves
    # admin_rows empty instead, and require_count refuses it.
    read -r admins admin_rows <<EOF
$admin_counts
EOF
    require_count "$admins" "the active-administrator count"
    require_count "$admin_rows" "the administrator count"

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
        # Not a pipeline, and not a stdout match. `... | tr | tail -n 1` keeps
        # only the LAST stage's exit status (see the note above alembic_cmd),
        # which would swallow a failure of the one state-changing command in
        # this script. And what init-admin writes to stdout is not a contract:
        # click 8.1.x echoes the hidden password prompt there, get_database()
        # prints its connection line into the same stream, and orm/setup.py
        # pins neither their order nor the click minor. The database is the
        # truth, so the same probe that got us here is what decides whether
        # this run produced an administrator.
        if compose exec -T server eorm init-admin --username "$admin_username" < "$pw_file"; then
            init_rc=0
        else
            init_rc=$?
        fi
        rm -f "$pw_file"
        trap - EXIT INT TERM
        admins=$(compose exec -T server python -c '
from eyened_orm import Database
from eyened_orm.authz.bootstrap import count_admins
with Database().get_session() as session:
    print(count_admins(session))
' | tr -d '\r' | tail -n 1)
        require_count "$admins" "the active-administrator count after init-admin"
        if [ "$init_rc" != "0" ] || [ "$admins" = "0" ]; then
            die "bootstrap: 'eorm init-admin' exited $init_rc and this database now reports
      $admins active administrator(s), so no password is printed here.
      An account may exist whose password was set to the one this run
      generated and has now discarded — inspect it by hand before assuming
      it does not, and run:
          cd deploy && $COMPOSE_BIN exec server eorm init-admin --username \"$admin_username\""
        fi
        cat <<EOF

------------------------------------------------------------------------
An administrator account was created. This password is shown ONCE:

    username: $admin_username
    password: $admin_password

Copy it now. More users can be created from the user interface.
------------------------------------------------------------------------
EOF
    elif [ "$admins" = "0" ]; then
        # Refuse loudly, never promote. ensure_admin() resets an existing
        # account's password whenever a supplied password does not already
        # verify (orm/eyened_orm/authz/bootstrap.py) — handing this run's
        # freshly generated password to an existing '$admin_username' account
        # would silently change that account's password. Only an operator who
        # deliberately means to do that should run init-admin themselves.
        #
        # Two states here, and they need two different commands: init-admin
        # promotes an account but never clears Inactive (ensure_admin()'s
        # `reactivate` is opt-in and init-admin does not pass it), so naming it
        # where the only administrators are deactivated would reset a real
        # user's password and still leave count_admins() at 0 — the next run
        # would refuse identically. 'eorm reactivate' is the recovery path.
        if [ "$admin_rows" = "0" ]; then
            die "bootstrap: $accounts account(s) already exist and NONE of them is an
      administrator. Nobody can administer this stack, and bootstrap will not
      promote an existing account automatically.
      Fix: run
          cd deploy && $COMPOSE_BIN exec server eorm init-admin --username \"$admin_username\"
      and follow its prompts."
        fi
        die "bootstrap: $accounts account(s) already exist, $admin_rows of them with
      administrator rights — but every one of those is DEACTIVATED, so nobody
      can administer this stack. bootstrap will not reactivate an account
      automatically, and 'eorm init-admin' would not reactivate one either.
      Fix: reactivate the deactivated administrator by name (replace it below
      if it is not '$admin_username'):
          cd deploy && $COMPOSE_BIN exec server eorm reactivate --user \"$admin_username\""
    else
        echo "bootstrap: $accounts account(s) exist, $admins of them an active administrator — nothing to do."
    fi
fi
