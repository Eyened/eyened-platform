#!/bin/sh
# Restore a snapshot written by db-snapshot.sh, replacing the data volume.
#
# Usage: db-restore.sh <name>
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

name=${1:-}
[ -n "$name" ] || die "usage: make db-restore NAME=<name>"

# Same lookup as db-snapshot.sh — resolve the volume from the container, never
# by rebuilding "${project}_db_data" (compose normalises project names).
cid=$(compose ps -q database || true)
[ -n "$cid" ] || die "error: this stack has no 'database' container to restore into."

volume=$(docker inspect "$cid" \
    --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}')
[ -n "$volume" ] || die "error: the database container has no named volume at /var/lib/mysql."

archive="$DEPLOY_DIR/snapshots/$name.tgz"
[ -f "$archive" ] || die "error: no snapshot at $archive"

printf "Replace the contents of volume %s from %s? [y/N] " "$volume" "$name.tgz"
read -r answer
case "$answer" in y|Y|yes|YES) ;; *) die "cancelled." ;; esac

# Same reasoning as db-snapshot.sh: an interrupt here has a worse window,
# since the datadir may already have been wiped by the time it lands. INT and
# TERM are trapped explicitly because an EXIT trap alone does not fire on a
# signal in every shell this might run under.
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

docker run --rm \
    -v "$volume:/data" \
    -v "$DEPLOY_DIR/snapshots:/in:ro" \
    alpine sh -c "rm -rf /data/* /data/..?* 2>/dev/null; tar xzf /in/$name.tgz -C /data"

echo "==> starting the database"
compose start database
restarted=1
trap - EXIT INT TERM
echo "restored from $archive"
