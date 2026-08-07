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

# NAME is interpolated into a file path AND into a container's `sh -c`
# string below, so anything outside this set (in particular `;`, `/`, `..`)
# is refused rather than reaching either.
case "$name" in
    *[!A-Za-z0-9._-]*) die "error: NAME '$name' contains characters other than
      letters, digits, '.', '_' and '-'.
      Pick a name matching [A-Za-z0-9._-]." ;;
esac

# Ask the container which mount it actually has, rather than rebuilding the
# volume name as "${project}_db_data". Compose normalises project names
# (lowercasing and stripping characters), so a COMPOSE_PROJECT_NAME like
# "Eyened.Kaustav" makes the string-built name wrong and yields an opaque "no
# such volume" from `docker run` instead of a usable error.
#
# `-a`, not a bare `ps -q`: a plain `compose ps -q` only lists RUNNING
# containers, so a database a previous db-restore.sh left deliberately
# stopped (see the mid-restore case in cleanup() below) would be invisible
# here — the exact container this script most needs to find in order to
# snapshot or re-restore it. `-a` also matches a container in any other
# non-running state (created, exited from a crash), which is never wrong to
# find: an absent 'database' service (never started, or no 'local-db'
# profile) still resolves to nothing either way.
cid=$(compose ps -a -q database || true)
[ -n "$cid" ] || die "error: this stack has no 'database' container.
      Either it has never been started, or it uses an external database
      (no 'local-db' profile) — in which case there is nothing here to
      snapshot. See deploy/README.md on backing up an external database
      before migrating."

# A durable deployment sets DB_DATA_PATH (see compose.yaml), which makes
# /var/lib/mysql a bind mount, not a named volume — `.Name` is empty for
# those. Resolve `.Type` first, then pull the right identifier: `.Name` for
# a named volume, `.Source` (the host path) for a bind mount. `docker run
# -v` accepts either in the same position.
mount_type=$(docker inspect "$cid" \
    --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Type}}{{end}}{{end}}')
case "$mount_type" in
    volume)
        mount_src=$(docker inspect "$cid" \
            --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}')
        mount_desc="volume $mount_src"
        ;;
    bind)
        mount_src=$(docker inspect "$cid" \
            --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Source}}{{end}}{{end}}')
        mount_desc="bind mount $mount_src"
        ;;
    *)
        mount_src=""
        ;;
esac
[ -n "$mount_src" ] || die "error: the database container has no volume or bind
      mount at /var/lib/mysql, so there is nothing to snapshot."

out="$DEPLOY_DIR/snapshots"
mkdir -p "$out"

if [ -e "$out/$name.tgz" ]; then
    die "error: $out/$name.tgz already exists.
      Pick another NAME, or remove it first if you mean to replace it."
fi

# If interrupted (Ctrl-C, a dropped SSH connection, or an operator's `kill`)
# or the docker run below fails, the database must not be left stopped and
# silent — this is meant to be the safety net for `make migrate`, not a
# second way to lose the database. The EXIT trap alone would not fire on a
# signal in every shell that might run this (see lib.sh header: nothing here
# may assume bash), so INT, TERM and HUP are trapped explicitly too — HUP
# specifically because a dropped SSH session sends the foreground process
# group SIGHUP, and this is exactly the kind of multi-minute command an
# operator runs over SSH.
#
# A trap that only runs `cleanup` and returns does NOT stop the script — the
# shell resumes at the next statement, so a signal during `compose stop
# database` would restart the database via the trap and then carry on into
# the destructive `tar` step below as if nothing happened (measured: dash,
# bash and busybox sh all resume this way). The INT/TERM/HUP handlers below
# run `cleanup`, restore the signal's default action, then re-raise it
# against this process so the shell actually dies instead of limping
# forward. `cleanup` stays idempotent (guarded by $restarted) because the
# re-raise can also trigger the EXIT trap.
restarted=0
cleanup() {
    if [ "$restarted" -eq 0 ]; then
        restarted=1
        echo "==> interrupted or failed: restarting the database" >&2
        compose start database || echo "error: could not restart the database — start it by hand: (cd deploy && $COMPOSE_BIN start database)" >&2
    fi
}
trap cleanup EXIT
trap 'cleanup; trap - INT; kill -INT $$' INT
trap 'cleanup; trap - TERM; kill -TERM $$' TERM
trap 'cleanup; trap - HUP; kill -HUP $$' HUP

echo "==> stopping the database"
compose stop database

echo "==> writing $out/$name.tgz from $mount_desc"
# Written under a .part suffix and moved into place inside the SAME `docker
# run`, so an aborted run never leaves a truncated file under the final name
# — db-restore.sh trusts that anything named $name.tgz is complete.
#
# The container itself stays root (the default): MySQL's datadir files are
# owned by the mysql user inside the volume (uid 999) and are not
# world-readable, so reading them as this host user would fail outright —
# measured, every file in the tar came back "Permission denied". Root can
# read the volume AND chown the finished archive to the invoking host user
# before it is moved into place, which is what actually fixes the
# root-owned-snapshot problem without breaking the read.
docker run --rm \
    -v "$mount_src:/data:ro" \
    -v "$out:/out" \
    alpine sh -c "tar czf /out/$name.tgz.part -C /data . && chown $(id -u):$(id -g) /out/$name.tgz.part && mv /out/$name.tgz.part /out/$name.tgz"

echo "==> starting the database"
compose start database
restarted=1
trap - EXIT INT TERM HUP
echo "snapshot written: $out/$name.tgz"
