#!/usr/bin/env bash
# Load a prepared XtraBackup directory into the compose MySQL data volume.
# Usage: ./load_dump.sh /absolute/path/to/backup-dir   (or relative to deploy/, e.g. tmp)
# The backup must already be prepared (xtrabackup --prepare). Run from anywhere;
# paths are resolved relative to deploy/.
set -euo pipefail

# Compose (and .env) live in deploy/, one level up from scripts/.
DIR="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  echo "usage: $0 <backup-dir>" >&2
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    ( cd "$DIR" && docker compose "$@" )
  elif command -v docker-compose >/dev/null 2>&1; then
    ( cd "$DIR" && docker-compose "$@" )
  else
    echo "error: neither 'docker compose' nor 'docker-compose' is available" >&2
    exit 1
  fi
}

if [ -z "${1:-}" ]; then
  usage
  exit 1
fi
SRC="$1"

# Bind mounts require an absolute host path; resolve relative paths against deploy/
if [[ "$SRC" != /* ]]; then
  SRC="$DIR/${SRC#./}"
fi

[ -d "$SRC" ] || { echo "error: not a directory: $SRC" >&2; exit 1; }

# Validate the source BEFORE anything is destroyed. The container command
# below runs `rm -rf /var/lib/mysql/*` first and only then lets
# `xtrabackup --copy-back` look at /restore, so a wrong or unprepared
# directory took the datadir with it before the error was even printed — the
# only host-side check was the `[ -d ]` above.
#
# xtrabackup_checkpoints is the marker, and this is measured against
# percona/percona-xtrabackup:8.0 (xtrabackup 8.0.35-36), the image this
# script runs, not inferred:
#   * `xtrabackup --backup` writes it with `backup_type = full-backuped`;
#     `xtrabackup --prepare` rewrites the same line to `full-prepared`.
#   * `--copy-back` reads ./xtrabackup_checkpoints first of all ("cannot open
#     ./xtrabackup_checkpoints" against a directory without it).
#   * Given `full-backuped` OR `log-applied` (what `--prepare --apply-log-only`
#     leaves), `--copy-back` refuses with "The target is not fully prepared.
#     Please prepare it without option --apply-log-only" and copies nothing.
#     Given `full-prepared` it restores.
# So `full-prepared` is exactly xtrabackup's own accept/reject boundary: this
# check rejects nothing --copy-back would have accepted, it only moves the
# refusal to before the wipe instead of after it.
checkpoints="$SRC/xtrabackup_checkpoints"
if [ ! -f "$checkpoints" ]; then
  echo "error: $SRC has no xtrabackup_checkpoints, so it is not an xtrabackup" >&2
  echo "       backup directory. Nothing was changed." >&2
  exit 1
fi
backup_type=$(sed -n 's/^backup_type[[:space:]]*=[[:space:]]*//p' "$checkpoints" | tr -d '[:space:]')
if [ "$backup_type" != "full-prepared" ]; then
  echo "error: the dump at $SRC is not prepared (backup_type = '${backup_type:-<unreadable>}';" >&2
  echo "       'full-prepared' is required). xtrabackup --copy-back would refuse it," >&2
  echo "       but only after this script had already emptied the data directory." >&2
  echo "       Fix: run 'xtrabackup --prepare --target-dir=$SRC' first." >&2
  echo "       Nothing was changed." >&2
  exit 1
fi

# Same confirmation db-restore.sh asks for, and for the same reason: this
# replaces a whole MySQL datadir and there is no undo.
#
# `|| answer=""` makes every read that does not complete a line — a piped or
# cron run with nothing on stdin, a closed terminal, an answer truncated by
# EOF — fall into the cancel branch with a message, rather than abort under
# `set -e` with no output. It can only ever refuse: the one input it turns
# away that a human meant as consent is a `y` with no newline after it
# (`printf y | ...`), and refusing a destructive restore is the safe side of
# that trade.
printf "Replace this stack's ENTIRE MySQL data directory from %s? [y/N] " "$SRC"
read -r answer || answer=""
case "$answer" in y|Y|yes|YES) ;; *) echo "cancelled — nothing was changed." >&2; exit 1 ;; esac

compose stop database

compose --profile backup run --rm --user 0:0 \
  -v "$SRC:/restore" \
  --entrypoint bash \
  xtrabackup -c 'set -euo pipefail
rm -rf /var/lib/mysql/*
xtrabackup --copy-back --target-dir=/restore --datadir=/var/lib/mysql
chown -R 999:999 /var/lib/mysql'

compose start database
