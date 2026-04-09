#!/usr/bin/env bash
# Hot backup of the compose MySQL volume: xtrabackup --backup then --prepare into DEST.
# Usage: ./save_dump.sh [-e envfile] <output-dir>
#   Default env is database/.env; paths are resolved relative to database/ (e.g. -e .env.dump tmp).
# Requires: database running; EYENED_DATABASE_USER and EYENED_DATABASE_PASSWORD in the env file.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/.env"

usage() {
  echo "usage: $0 [-e envfile] <output-dir>" >&2
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
  echo "  <output-dir>: absolute path or path under database/ (e.g. tmp)" >&2
  exit 1
fi
DEST="$1"

# Resolve relative env file path against database/
if [[ "$ENV_FILE" != /* ]]; then
  ENV_FILE="$DIR/${ENV_FILE#./}"
fi

# Bind mounts require an absolute host path; resolve relative paths against database/
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