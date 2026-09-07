#!/bin/sh
# Hot backup of the bundled MySQL datadir: xtrabackup --backup, then
# --prepare, into <output-dir>. The database keeps serving throughout.
#
#   ./eyened backup [-t] <output-dir>
#   deploy/scripts/db-backup.sh [-e envfile] [-t] <output-dir>
#
# -t also writes <output-dir>.tgz, so moving a backup to another machine is
# one scp. db-restore.sh accepts either form.
#
# The output is a raw InnoDB datadir, NOT logical SQL, so the destination must
# run a compatible MySQL 8.0 — satisfied by construction, since compose.yaml
# pins mysql:8.0.46. For a portable, cross-version dump, or for a database
# this stack does not own, use the HOST tool `eorm save_dump` instead. See
# deploy/README.md; the two are different mechanisms with different restore
# semantics, which is why they no longer share a name.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

ENV_FILE="$DEPLOY_DIR/.env"
TAR=no

USAGE="usage: db-backup.sh [-e envfile] [-t] <output-dir>
      <output-dir>  an absolute path, or a path under deploy/ (e.g. backups)
      -e envfile    read credentials from this file instead of deploy/.env
      -t            also write <output-dir>.tgz"

usage() {
    die "$USAGE"
}

while getopts "e:th" opt; do
    case "$opt" in
        e) ENV_FILE=$OPTARG ;;
        t) TAR=yes ;;
        h) printf '%s\n' "$USAGE"; exit 0 ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))

DEST=${1:-}
[ -n "$DEST" ] || usage

# getopts stops at the first non-option word, so with the flag AFTER the
# positional (`db-backup.sh /srv/bk -t`) OPTIND never reaches '-t': it is
# left sitting unconsumed in $2, TAR stays 'no', and nothing says so. Refuse
# rather than silently ignore it — the documented order (see the header and
# $USAGE above) is flags first.
shift
[ $# -eq 0 ] || die "error: unexpected extra argument(s) after <output-dir>: $*
      Fix: options come before the output directory, e.g.
           db-backup.sh [-e envfile] [-t] <output-dir>."

# Bind mounts need an absolute host path; resolve relative paths against deploy/.
case "$ENV_FILE" in /*) ;; *) ENV_FILE="$DEPLOY_DIR/${ENV_FILE#./}" ;; esac
case "$DEST"     in /*) ;; *) DEST="$DEPLOY_DIR/${DEST#./}" ;; esac

# Refuse to write into the checkout unless git ignores the destination. This
# is a public repository: 'git add -A' would otherwise pick up a raw MySQL
# datadir (potentially patient data) written under it. A DEST outside the
# checkout entirely is not this repo's problem, so the case below only ever
# looks at $REPO_ROOT itself and paths under it.
#
# `git check-ignore -q` does not require DEST to exist for an ordinary
# pattern, but it DOES for a directory-only one ('foo/', trailing slash):
# such a pattern only matches once git can tell the path is a directory,
# which for a not-yet-created DEST means "not yet, until something creates
# it" — measured directly against this .gitignore's own entry, which is why
# it is 'deploy/backups' with no trailing slash rather than 'deploy/backups/'.
# Separately, on a path it cannot place inside REPO_ROOT at all,
# check-ignore exits 128 with a `fatal:` — which is exactly why the case
# below gates on the path prefix itself rather than trusting check-ignore's
# own exit status to tell "outside" apart from "not ignored".
case "$DEST" in
    "$REPO_ROOT"|"$REPO_ROOT"/*)
        # `cmd || rc=$?`, not a bare `cmd` followed by `$?`: under this
        # script's `set -e`, a plain non-zero simple command exits the whole
        # script immediately — before a following `case "$?"` is ever
        # reached — which would silently turn "not ignored" into a bare
        # exit 1 with no message at all. Measured directly.
        _gi_rc=0
        git -C "$REPO_ROOT" check-ignore -q "$DEST" 2>/dev/null || _gi_rc=$?
        case "$_gi_rc" in
            0) ;;
            1) die "error: $DEST is inside this checkout and git does not ignore it.
      Writing a backup there risks 'git add' picking up a raw MySQL datadir
      in a public repository.
      Fix: use a path under deploy/backups/ (already gitignored), or an
           absolute path outside the checkout." ;;
            *) die "error: could not tell whether git ignores $DEST
      ('git check-ignore' exited abnormally).
      Fix: check that $REPO_ROOT is a git checkout, or pass a path outside
           it." ;;
        esac
        ;;
    *) ;;
esac

# This stack must own a database before any of this makes sense. On an
# external-database deployment ('./eyened prod', no 'local-db' profile) no
# 'database' service resolves at all (D1's CI invariant), so the schema
# probe below would instead read whatever unrelated, unconnected volume
# ${DB_DATA_PATH:-db_data} happens to name and report a false 'missing'
# schema with advice ("create the schema first") that is wrong for that
# deployment. Checked here, after argument parsing (so a bad invocation or
# '-h' never has to touch Docker) and before anything that does.
#
# `compose ps -a -q database`, not a COMPOSE_PROFILES text check: this asks
# compose itself, so it can't disagree with what 'down -v' (reset.sh) or D1's
# own external-database case resolve to, even when COMPOSE_PROFILES was
# overridden from the calling shell rather than deploy/.env (see reset.sh's
# header comment on that divergence). Same mechanism the deleted cold-tar
# db-snapshot.sh used. `-a`, not a bare `ps -q`: a stopped-but-existing
# container (this stack owns a database that just isn't running right now)
# must not be misdiagnosed as "external".
#
# An empty result here is ambiguous between "external database" and "never
# started" — measured: both give an empty, zero-status `ps -a -q database`
# when no container has ever been created — so the message below names both.
cid=$(compose ps -a -q database) || cid=""
[ -n "$cid" ] || die "error: this stack has no 'database' container. Either it has never
      been started, or it uses an external database (no 'local-db' profile)
      — in which case there is nothing here for db-backup.sh to back up.
      Fix: run './eyened up' first if you meant to create one, or back up an
           external database with its own tooling ('eorm save_dump'). See
           deploy/README.md's 'Backup and rollback' section."

[ -f "$ENV_FILE" ] || die "error: $ENV_FILE does not exist, so there are no database
      credentials to back up with.
      Fix: run './eyened install' or './eyened up' first, or pass -e <envfile>."

# env_get, and NOT `set -a; . "$ENV_FILE"` as this script used to do. An env
# file is not a shell script: a password containing an unquoted shell
# metacharacter — a bare '(' is enough — makes sourcing abort with a syntax
# error pointing at a line this script does not own, and under `set -e` that
# ends the run with no message of its own. Measured on a real .env. env_get
# reads one assignment with sed and has no opinion on the value.
DB_USER=$(env_get EYENED_DATABASE_USER "$ENV_FILE")
DB_PASS=$(env_get EYENED_DATABASE_PASSWORD "$ENV_FILE")
DB_NAME=$(env_get EYENED_DATABASE_DATABASE "$ENV_FILE")
[ -n "$DB_NAME" ] || DB_NAME=eyened_database   # compose.yaml's own default

[ -n "$DB_USER" ] && [ -n "$DB_PASS" ] ||
    die "error: EYENED_DATABASE_USER and EYENED_DATABASE_PASSWORD must both be
      set in $ENV_FILE, and at least one is empty.
      Fix: check $ENV_FILE, or pass a different one with -e."

# Is there actually a schema in there? mysqld initialises its own system
# tables whether or not anyone ran bootstrap, so a backup taken before that
# looks entirely plausible — measured on the cold-tar path this replaces: a
# 5.5 MB archive whose eyened_database/ held no .ibd files at all, reported as
# a successful snapshot. db-restore.sh trusts whatever it is handed, so an
# empty backup is a loaded gun aimed at the populated database it is later
# restored over.
#
# Read off the datadir rather than asking SQL: no credentials, no client, and
# no dependency on the server container — the state this catches (nobody ran
# bootstrap) is exactly the state in which the server is least trustworthy.
#
# It runs INSIDE the xtrabackup service, which this script needs anyway and
# which already mounts ${DB_DATA_PATH:-db_data} at /var/lib/mysql: the same
# source as `database`, deliberately (compose.yaml). The cold-tar version used
# `docker inspect` plus a plain `docker run … alpine` to resolve that mount by
# hand; going through the service instead is what lets this script need no
# image beyond the one it already pulls.
schema_state=$(compose --profile backup run --rm --user 0:0 \
    -e SNAP_DB="$DB_NAME" \
    --entrypoint sh \
    xtrabackup -c '
if [ ! -d "/var/lib/mysql/$SNAP_DB" ]; then
    echo missing
else
    set -- "/var/lib/mysql/$SNAP_DB"/*.ibd
    if [ -e "$1" ]; then echo ok; else echo empty; fi
fi' 2>/dev/null | tr -d "\r" | tail -n 1) || schema_state=""

# The SHAPE of the answer is the guard, not the pipeline's exit status. POSIX
# sh has no `pipefail`, so a failed `compose run` disappears behind `tail`,
# which exits 0 on empty input — the same trap bootstrap.sh documents. Any
# value that is not one of the three expected words is refused below, and an
# empty string is one of those.
case "$schema_state" in
    ok) ;;
    missing|empty)
        case "$schema_state" in
            missing) _why="has no '$DB_NAME' directory at all" ;;
            *)       _why="has a '$DB_NAME' directory holding no tables (no .ibd files)" ;;
        esac
        die "error: this stack's database datadir $_why, so
      the schema has never been created here — there is nothing to back up.
      Writing one anyway would produce a backup of MySQL's own system tables
      and nothing else, which db-restore.sh would later accept as complete.
      Fix: create the schema first — './eyened install' or './eyened up'. Both
           run bootstrap; a bare '$COMPOSE_BIN up -d' does not, which is how a
           stack ends up serving traffic on an empty database." ;;
    *)
        die "error: could not tell whether the datadir holds a schema — the probe
      returned '$schema_state' instead of ok, missing or empty. Refusing to
      write a backup that may be empty.
      Fix: check that the stack is up and the 'backup' profile can run:
           (cd $DEPLOY_DIR && $COMPOSE_BIN --profile backup run --rm xtrabackup --version)" ;;
esac

mkdir -p "$(dirname "$DEST")" ||
    die "error: could not create $(dirname "$DEST").
      Fix: check permissions on its parent directory, or pass a different
           <output-dir>."

# $DEST is operator-supplied and the next line is a recursive delete of it, so
# 'db-backup.sh /home/user' used to wipe a home directory without asking.
# Confirm before destroying anything — and only when there IS something to
# destroy, so the ordinary "write a new backup" case stays one command.
#
# `|| answer=""` makes every read that does not complete a line — a piped or
# cron run with nothing on stdin, a closed terminal, an answer truncated by
# EOF — fall into the cancel branch with a message rather than abort under
# `set -e` with no output. It can only ever refuse.
if [ -e "$DEST" ]; then
    printf "DELETE %s and everything under it, then write the backup there? [y/N] " "$DEST"
    read -r answer || answer=""
    case "$answer" in y|Y|yes|YES) ;; *) die "cancelled — nothing was removed." ;; esac
fi

rm -rf "$DEST"
mkdir -p "$DEST" || die "error: could not create $DEST.
      Fix: check permissions on $(dirname "$DEST"), or pass a different
           <output-dir>."

# -e for the container, because docker-compose v1 has no --env-file on `run`.
# \$ expands inside the container, not here.
compose --profile backup run --rm --user 0:0 \
    -e EYENED_DATABASE_USER="$DB_USER" \
    -e EYENED_DATABASE_PASSWORD="$DB_PASS" \
    -v "$DEST:/backup-out" \
    --entrypoint sh \
    xtrabackup -c 'set -eu
xtrabackup --backup \
  --host=database \
  --user=${EYENED_DATABASE_USER} \
  --password=${EYENED_DATABASE_PASSWORD} \
  --target-dir=/backup-out
xtrabackup --prepare --target-dir=/backup-out'

# xtrabackup writes as root inside the container; hand the result back so the
# invoking user can read, tar or scp their own backup.
if [ "$(id -u)" != 0 ]; then
    compose --profile backup run --rm --user 0:0 \
        -e OWNER="$(id -u):$(id -g)" \
        -v "$DEST:/backup-out" \
        --entrypoint sh \
        xtrabackup -c 'chown -R "$OWNER" /backup-out' ||
        echo "warning: could not chown $DEST back to $(id -u):$(id -g) — read it with sudo." >&2
fi

echo "==> prepared backup: $DEST"

if [ "$TAR" = yes ]; then
    tar czf "$DEST.tgz" -C "$(dirname "$DEST")" "$(basename "$DEST")" ||
        die "error: the backup at $DEST is complete, but tarring it to $DEST.tgz
      failed (see above).
      Fix: tar it by hand, or scp the directory itself."
    echo "==> single-file copy: $DEST.tgz"
fi
