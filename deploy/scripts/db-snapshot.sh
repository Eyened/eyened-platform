#!/bin/sh
# Cold snapshot of the bundled MySQL data volume.
#
# Cold, not hot, on purpose: MySQL auto-commits DDL per statement, so a
# half-applied migration cannot be reliably undone with `alembic downgrade`.
# This is the safety net for `make migrate`.
#
# Usage: db-snapshot.sh <name>
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

name=${1:-}
[ -n "$name" ] || die "usage: make db-snapshot NAME=<name>"

# Ask the container which volume it actually has, rather than rebuilding the
# name as "${project}_db_data". Compose normalises project names (lowercasing
# and stripping characters), so a COMPOSE_PROJECT_NAME like "Eyened.Kaustav"
# makes the string-built name wrong and yields an opaque "no such volume" from
# `docker run` instead of a usable error.
cid=$(compose ps -q database || true)
[ -n "$cid" ] || die "error: this stack has no 'database' container.
      Either it has never been started, or it uses an external database
      (no 'local-db' profile) — in which case there is nothing here to
      snapshot. See deploy/README.md on backing up an external database
      before migrating."

volume=$(docker inspect "$cid" \
    --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}')
[ -n "$volume" ] || die "error: the database container has no named volume at
      /var/lib/mysql, so there is nothing to snapshot."

out="$DEPLOY_DIR/snapshots"
mkdir -p "$out"

# If interrupted (Ctrl-C) or the docker run below fails, the database must not
# be left stopped and silent — this is meant to be the safety net for `make
# migrate`, not a second way to lose the database. The EXIT trap alone would
# not fire on a signal in every shell that might run this (see lib.sh header:
# nothing here may assume bash), so INT and TERM are trapped explicitly too.
restarted=0
cleanup() {
    if [ "$restarted" -eq 0 ]; then
        restarted=1
        echo "==> interrupted or failed: restarting the database" >&2
        compose start database || echo "error: could not restart the database — start it by hand: (cd deploy && $COMPOSE_BIN start database)" >&2
    fi
}
trap cleanup EXIT INT TERM

echo "==> stopping the database"
compose stop database

echo "==> writing $out/$name.tgz from volume $volume"
docker run --rm \
    -v "$volume:/data:ro" \
    -v "$out:/out" \
    alpine tar czf "/out/$name.tgz" -C /data .

echo "==> starting the database"
compose start database
restarted=1
trap - EXIT INT TERM
echo "snapshot written: $out/$name.tgz"
