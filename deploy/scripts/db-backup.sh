#!/bin/sh
# Hot backup of the bundled MySQL datadir: xtrabackup --backup, then
# --prepare, into <output-dir>. The database keeps serving throughout.
#
#   ./eyened backup <output-dir> [-t]
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

usage() {
    die "usage: db-backup.sh [-e envfile] [-t] <output-dir>
      <output-dir>  an absolute path, or a path under deploy/ (e.g. tmp)
      -e envfile    read credentials from this file instead of deploy/.env
      -t            also write <output-dir>.tgz"
}

while getopts "e:th" opt; do
    case "$opt" in
        e) ENV_FILE=$OPTARG ;;
        t) TAR=yes ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))

DEST=${1:-}
[ -n "$DEST" ] || usage

# Bind mounts need an absolute host path; resolve relative paths against deploy/.
case "$ENV_FILE" in /*) ;; *) ENV_FILE="$DEPLOY_DIR/${ENV_FILE#./}" ;; esac
case "$DEST"     in /*) ;; *) DEST="$DEPLOY_DIR/${DEST#./}" ;; esac

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
    die "error: could not create $(dirname "$DEST")."

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
mkdir -p "$DEST" || die "error: could not create $DEST."

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
