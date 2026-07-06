#!/usr/bin/env bash
# Load a prepared XtraBackup directory into the compose MySQL data volume.
# Usage: ./load_dump.sh /absolute/path/to/backup-dir   (or relative to database/, e.g. tmp)
# The backup must already be prepared (xtrabackup --prepare). Intended to be run from database/.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
  echo "usage: $0 <backup-dir>" >&2
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
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

# Bind mounts require an absolute host path; resolve relative paths against database/
if [[ "$SRC" != /* ]]; then
  SRC="$DIR/${SRC#./}"
fi

[ -d "$SRC" ] || { echo "error: not a directory: $SRC" >&2; exit 1; }

compose stop database

compose --profile backup run --rm --user 0:0 \
  -v "$SRC:/restore" \
  --entrypoint bash \
  xtrabackup -c 'set -euo pipefail
rm -rf /var/lib/mysql/*
xtrabackup --copy-back --target-dir=/restore --datadir=/var/lib/mysql
chown -R 999:999 /var/lib/mysql'

compose start database
