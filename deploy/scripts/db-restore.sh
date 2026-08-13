#!/bin/sh
# Restore a snapshot written by db-snapshot.sh, replacing the data volume.
#
# Usage: make db-restore NAME=<name>
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

# `-a` can also match more than one id: a leftover `docker compose run
# database ...` one-off container is included alongside the real service
# container. Left unguarded, the `docker inspect` calls below would fail on
# whichever id happens to come first with a raw "No such object" instead of
# a `die` naming the actual problem.
case "$(printf '%s\n' "$cid" | wc -l | tr -d ' ')" in
    1) ;;
    *) die "error: found more than one 'database' container:
$cid
      This is usually a leftover 'docker compose run database ...' one-off
      alongside the real service container.
      Fix: remove the extra one, e.g. '(cd deploy && $COMPOSE_BIN rm -f
      <container-id>)', so exactly one 'database' container remains, then
      re-run make db-restore." ;;
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
# $wipe_started used to be a HOST-side flag, set immediately before the
# `docker run` below and cleared immediately after, and cleanup() read it to
# decide whether the datadir is INCONSISTENT. That tracked the host's INTENT
# to run the wipe, not whether the wipe actually happened: a `docker run`
# that fails before touching anything — an unavailable image is the
# realistic case, since this is exactly the script that runs on a fresh DR
# host and nothing else in the stack pulls `alpine` — still set the flag, so
# cleanup() reported "INCONSISTENT... previous contents were removed"
# against a datadir that was never touched (measured directly). The same gap
# existed at the other end: a signal landing after a fully successful
# `docker run` returns, but before the host's next statement cleared the
# flag, reported the same false INCONSISTENT message against a fully
# restored datadir.
#
# Fixed by moving the source of truth INSIDE the container instead of
# tracking host-side timing at all. $sentinel_dir is a host-owned scratch
# directory bind-mounted at /state; the container itself touches
# /state/wiping immediately before `rm -rf` and removes it immediately after
# `tar xzf` succeeds. cleanup() below tests for that file's presence. A
# `docker run` that never got far enough to run `touch` leaves no file
# (correctly read as untouched); a `docker run` that finished the whole `&&`
# chain has already removed it before control returns to the host, so there
# is no timing window left in which a signal can land between "the work
# finished" and "the host notices" — the file's state on disk IS the
# datadir's state, not a proxy the host has to keep in sync by hand.
restarted=0
sentinel_dir="${TMPDIR:-/tmp}/db-restore-state.$$"
mkdir "$sentinel_dir" || die "error: could not create a temp directory at
      $sentinel_dir to track restore progress.
      Fix: check that ${TMPDIR:-/tmp} exists and is writable."
cleanup() {
    if [ "$restarted" -eq 0 ]; then
        restarted=1
        if [ -e "$sentinel_dir/wiping" ]; then
            printf '%s\n' "==> interrupted mid-restore: the datadir for $mount_desc is now
      INCONSISTENT — the previous contents were removed and the archive was
      only partially extracted. The database has been left STOPPED on
      purpose: starting MySQL on a half-written datadir risks it coming up
      on corrupt files instead of failing loudly.
      Fix: re-run 'make db-restore NAME=$name' to finish the restore before
      using this database again." >&2
        else
            echo "==> interrupted or failed: restarting the database" >&2
            compose start database || echo "error: could not restart the database — start it by hand: (cd deploy && $COMPOSE_BIN start database)" >&2
        fi
    fi
    rm -rf "$sentinel_dir" 2>/dev/null
}
trap cleanup EXIT
trap 'cleanup; trap - INT; kill -INT $$' INT
trap 'cleanup; trap - TERM; kill -TERM $$' TERM
trap 'cleanup; trap - HUP; kill -HUP $$' HUP

echo "==> stopping the database"
compose stop database

docker run --rm \
    -v "$mount_src:/data" \
    -v "$DEPLOY_DIR/snapshots:/in:ro" \
    -v "$sentinel_dir:/state" \
    alpine sh -c "touch /state/wiping; rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null; tar xzf /in/$name.tgz -C /data && rm -f /state/wiping"

echo "==> starting the database"
compose start database
restarted=1
trap - EXIT INT TERM HUP
rm -rf "$sentinel_dir" 2>/dev/null
echo "restored from $archive"
