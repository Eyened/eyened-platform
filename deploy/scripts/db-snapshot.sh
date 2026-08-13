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
# containers, so a database left deliberately STOPPED (for example by an
# interrupted db-restore.sh — see the mid-restore case in cleanup() in
# db-restore.sh) would be invisible here, and this script could not tell
# "stopped, do not touch" apart from "never existed". `-a` also matches a
# `created` container (one that has never been started) and other
# non-running states (exited from a crash, paused) — unlike in
# db-restore.sh, those are NOT safe to snapshot here: a `created` container
# has no data yet, and a stopped one may hold a datadir an interrupted
# restore left inconsistent on purpose. Measured: with `-a`, a `created`
# container DOES resolve to something (an 85-byte tarball of nothing, which
# this script would call a successful snapshot) — the RUNNING-state check
# below, not `-a` itself, is what keeps this script from acting on it.
cid=$(compose ps -a -q database || true)
[ -n "$cid" ] || die "error: this stack has no 'database' container.
      Either it has never been started, or it uses an external database
      (no 'local-db' profile) — in which case there is nothing here to
      snapshot. See deploy/README.md on backing up an external database
      before migrating."

# `-a` can also match more than one id: a leftover `docker compose run
# database ...` one-off container is included alongside the real service
# container. Left unguarded, the `docker inspect` calls below would fail on
# whichever id happens to come first with a raw "No such object" instead of
# a `die` naming the actual problem.
case "$(printf '%s\n' "$cid" | wc -l)" in
    1) ;;
    *) die "error: found more than one 'database' container:
$cid
      This is usually a leftover 'docker compose run database ...' one-off
      alongside the real service container.
      Fix: remove the extra one, e.g. '(cd deploy && $COMPOSE_BIN rm -f
      <container-id>)', so exactly one 'database' container remains, then
      re-run make db-snapshot." ;;
esac

# A cold snapshot needs the container actually RUNNING, not merely present.
# `-a` above only widens the lookup so this script can name a stopped
# container's state in the die below — it does not mean a stopped container
# is safe to tar. A `created` (never-started) container has an empty
# datadir; a stopped one may hold a datadir an interrupted db-restore.sh
# left INCONSISTENT on purpose (see F1 in db-restore.sh). Silently tarring
# either, then running the unconditional `compose start database` below,
# would call a broken snapshot successful and, in the second case, start
# mysqld on exactly the files db-restore.sh refuses to start.
status=$(docker inspect "$cid" --format '{{.State.Status}}') ||
    die "error: could not inspect the 'database' container's state (see
      above)."
case "$status" in
    running) ;;
    created)
        die "error: the 'database' container has been created but never
      started (state: created), so it has no data yet — there is nothing
      to snapshot.
      Fix: start it — (cd deploy && $COMPOSE_BIN up -d database) — or bring
      up the whole stack (make up), then re-run make db-snapshot." ;;
    *)
        die "error: the 'database' container is not running (state:
      $status). Snapshotting it now could tar an inconsistent datadir — for
      example one an interrupted db-restore.sh left stopped on purpose —
      and this script would then start mysqld on it afterwards as if
      nothing were wrong.
      Fix: find out why it is stopped first ('$COMPOSE_BIN ps', 'docker
      logs $cid'); once you are sure it is safe, start it —
      (cd deploy && $COMPOSE_BIN start database) — then re-run
      make db-snapshot." ;;
esac

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
