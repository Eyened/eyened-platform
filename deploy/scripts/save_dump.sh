#!/usr/bin/env bash
# Hot backup of the compose MySQL volume: xtrabackup --backup then --prepare into DEST.
# Usage: ./save_dump.sh [-e envfile] <output-dir>
#   Default env is deploy/.env; paths are resolved relative to deploy/ (e.g. -e .env.dump tmp).
# Requires: database running; EYENED_DATABASE_USER and EYENED_DATABASE_PASSWORD in the env file.
set -euo pipefail

# Compose (and .env) live in deploy/, one level up from scripts/.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$DIR/.env"

usage() {
  echo "usage: $0 [-e envfile] <output-dir>" >&2
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

while getopts "e:h" opt; do
  case "$opt" in
    e) ENV_FILE=$OPTARG ;;
    h) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

if [ -z "${1:-}" ]; then
  usage
  echo "  <output-dir>: absolute path or path under deploy/ (e.g. tmp)" >&2
  exit 1
fi
DEST="$1"

# Resolve relative env file path against deploy/
if [[ "$ENV_FILE" != /* ]]; then
  ENV_FILE="$DIR/${ENV_FILE#./}"
fi

# Bind mounts require an absolute host path; resolve relative paths against deploy/
if [[ "$DEST" != /* ]]; then
  DEST="$DIR/${DEST#./}"
fi

[ -f "$ENV_FILE" ] || { echo "error: missing $ENV_FILE" >&2; exit 1; }

# shellcheck source=/dev/null
set -a
. "$ENV_FILE"
set +a

[ -n "${EYENED_DATABASE_USER:-}" ] && [ -n "${EYENED_DATABASE_PASSWORD:-}" ] || {
  echo "error: set EYENED_DATABASE_USER and EYENED_DATABASE_PASSWORD in $ENV_FILE" >&2
  exit 1
}

mkdir -p "$(dirname "$DEST")"

# $DEST is an operator-supplied path and the next line is a recursive delete of
# it, so `./save_dump.sh /home/user` used to wipe a home directory without
# asking. Confirm before destroying anything — and only when there IS something
# to destroy, so the ordinary "write a new dump" case stays a single command.
#
# `|| answer=""` makes every read that does not complete a line — a piped or
# cron run with nothing on stdin, a closed terminal, an answer truncated by
# EOF — fall into the cancel branch with a message, rather than abort under
# `set -e` with no output. It can only ever refuse.
if [ -e "$DEST" ]; then
  printf "DELETE %s and everything under it, then write the dump there? [y/N] " "$DEST"
  read -r answer || answer=""
  case "$answer" in y|Y|yes|YES) ;; *) echo "cancelled — nothing was removed." >&2; exit 1 ;; esac
fi

rm -rf "$DEST"
mkdir -p "$DEST"

# -e for docker-compose v1 (no --env-file on run). \$ expands inside the container.
compose --profile backup run --rm --user 0:0 \
  -e EYENED_DATABASE_USER="$EYENED_DATABASE_USER" \
  -e EYENED_DATABASE_PASSWORD="$EYENED_DATABASE_PASSWORD" \
  -v "$DEST:/backup-out" \
  --entrypoint bash \
  xtrabackup -c "set -euo pipefail
xtrabackup --backup \
  --host=database \
  --user=\${EYENED_DATABASE_USER} \
  --password=\${EYENED_DATABASE_PASSWORD} \
  --target-dir=/backup-out
xtrabackup --prepare --target-dir=/backup-out
"

echo "==> prepared backup: $DEST"