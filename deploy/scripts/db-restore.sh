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

# NAME is interpolated into a file path AND into a container's `sh -c`
# string below, so anything outside this set (in particular `;`, `/`, `..`)
# is refused rather than reaching either.
case "$name" in
    *[!A-Za-z0-9._-]*) die "error: NAME '$name' contains characters other than
      letters, digits, '.', '_' and '-'.
      Pick a name matching [A-Za-z0-9._-]." ;;
esac

# Same lookup as db-snapshot.sh — resolve the mount from the container, never
# by rebuilding "${project}_db_data" (compose normalises project names).
#
# `-a`, not a bare `ps -q`: a plain `compose ps -q` only lists RUNNING
# containers. This script itself is the reason a stopped-but-existing
# database container is the common case to hit here — an interrupted restore
# leaves the database deliberately STOPPED (see the mid-restore case in
# cleanup() below) and tells the operator to re-run this exact script, which
# would otherwise immediately die with "no database container to restore
# into" instead of finding the very container it just stopped.
cid=$(compose ps -a -q database || true)
[ -n "$cid" ] || die "error: this stack has no 'database' container to restore into."

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
      mount at /var/lib/mysql."

archive="$DEPLOY_DIR/snapshots/$name.tgz"
[ -f "$archive" ] || die "error: no snapshot at $archive"

printf "Replace the contents of %s from %s? [y/N] " "$mount_desc" "$name.tgz"
read -r answer
case "$answer" in y|Y|yes|YES) ;; *) die "cancelled." ;; esac

# Same reasoning as db-snapshot.sh: an interrupt here has a worse window,
# since the datadir may already have been wiped by the time it lands. INT,
# TERM and HUP are trapped explicitly because an EXIT trap alone does not
# fire on a signal in every shell this might run under — HUP specifically
# because a dropped SSH session sends the foreground process group SIGHUP,
# and a restore is exactly the kind of command an operator runs over SSH.
#
# A trap that only runs `cleanup` and returns does NOT stop the script — the
# shell resumes at the next statement, so a signal during `compose stop
# database` would restart the (now running) database via the trap and then
# carry on into the `rm -rf`/`tar xzf` step below, wiping and extracting over
# a live datadir as if nothing happened (measured: dash, bash and busybox sh
# all resume this way). The INT/TERM/HUP handlers below run `cleanup`,
# restore the signal's default action, then re-raise it against this process
# so the shell actually dies instead of limping forward. `cleanup` stays
# idempotent (guarded by $restarted) because the re-raise can also trigger
# the EXIT trap.
#
# $wipe_started tracks a narrower, worse state than "interrupted": whether
# the destructive `rm -rf ... && tar xzf ...` step below has STARTED but not
# COMPLETED. In that state the datadir holds neither the old contents (wiped)
# nor the new ones (extraction unfinished) — silently running `compose start
# database` on it, the way the ordinary interrupted-before-the-wipe case
# does, would bring MySQL up on a half-written datadir while telling the
# operator "restarting the database" as if that were a recovery. It is not:
# cleanup below leaves the database STOPPED in that specific case and says so
# loudly, rather than start mysqld on files it cannot know are consistent.
restarted=0
wipe_started=0
cleanup() {
    if [ "$restarted" -eq 0 ]; then
        restarted=1
        if [ "$wipe_started" -eq 1 ]; then
            printf '%s\n' "==> interrupted mid-restore: the datadir for $mount_desc is now
      INCONSISTENT — the previous contents were removed and the archive was
      only partially extracted. The database has been left STOPPED on
      purpose: starting MySQL on a half-written datadir risks it coming up
      on corrupt files instead of failing loudly.
      Fix: re-run 'db-restore.sh $name' to finish the restore before using
      this database again." >&2
        else
            echo "==> interrupted or failed: restarting the database" >&2
            compose start database || echo "error: could not restart the database — start it by hand: (cd deploy && $COMPOSE_BIN start database)" >&2
        fi
    fi
}
trap cleanup EXIT
trap 'cleanup; trap - INT; kill -INT $$' INT
trap 'cleanup; trap - TERM; kill -TERM $$' TERM
trap 'cleanup; trap - HUP; kill -HUP $$' HUP

echo "==> stopping the database"
compose stop database

wipe_started=1
docker run --rm \
    -v "$mount_src:/data" \
    -v "$DEPLOY_DIR/snapshots:/in:ro" \
    alpine sh -c "rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null; tar xzf /in/$name.tgz -C /data"
wipe_started=0

echo "==> starting the database"
compose start database
restarted=1
trap - EXIT INT TERM HUP
echo "restored from $archive"
