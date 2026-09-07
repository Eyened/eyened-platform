#!/bin/sh
# Restore a prepared xtrabackup directory (or the .tgz db-backup.sh -t writes)
# into the bundled MySQL datadir. The database is stopped for the duration.
#
#   ./eyened restore <backup-dir|backup.tgz>
#
# The source must already be PREPARED (xtrabackup --prepare), which db-backup.sh
# does for you. There is no undo: this replaces the whole datadir.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

SRC=${1:-}
[ -n "$SRC" ] || die "usage: db-restore.sh <backup-dir|backup.tgz>"

# Bind mounts need an absolute host path; resolve relative paths against deploy/.
case "$SRC" in /*) ;; *) SRC="$DEPLOY_DIR/${SRC#./}" ;; esac

# Captured before the .tgz branch below can reassign SRC to a scratch
# directory that cleanup() deletes — the mid-restore recovery message names
# this, and it has to be something the operator can actually re-run
# db-restore.sh against, not the (by then removed) scratch directory.
ORIG_SRC=$SRC

# This is the exact scenario compose.yaml's xtrabackup service comment warns
# about: without this check, an external-database stack ('./eyened prod', no
# 'local-db' profile — D1) falls straight into 'compose stop database' below
# and then the wipe container, which mounts ${DB_DATA_PATH:-db_data}
# regardless of whether this stack owns a database at all. That volume is
# unrelated and (on a fresh host) empty, so the result is: wipe and restore
# into nothing, reported as success, while the live external database sits
# untouched. Checked here, after basic argument validation (so a bad
# invocation never has to touch Docker first) and before anything — in
# particular the tarball extraction below — that does.
#
# Same mechanism as db-backup.sh (see its header comment for why `compose ps
# -a -q database` rather than a COMPOSE_PROFILES text check), ported from the
# deleted cold-tar db-restore.sh, which opened with exactly this.
cid=$(compose ps -a -q database) || cid=""
[ -n "$cid" ] || die "error: this stack has no 'database' container. Either it has never
      been started, or it uses an external database (no 'local-db' profile)
      — in which case there is nothing here for db-restore.sh to restore
      into.
      Fix: run './eyened up' first if you meant to create one, or restore an
           external database with its own tooling. See deploy/README.md's
           'Backup and rollback' section."

# A .tgz written by 'db-backup.sh -t' is unpacked to a scratch directory first,
# so the rest of this script only ever deals with a directory. Accepting the
# tarball here rather than telling the operator to untar it by hand is the
# whole point of the -t flag: cross-machine transport stays one scp and one
# command.
untarred=""
if [ -f "$SRC" ]; then
    case "$SRC" in
        *.tgz|*.tar.gz)
            untarred=$(mktemp -d) ||
                die "error: could not create a temp directory to unpack $SRC.
      Fix: check that ${TMPDIR:-/tmp} exists and is writable."
            tar xzf "$SRC" -C "$untarred" ||
                { rm -rf "$untarred"; die "error: could not unpack $SRC (see above).
      Fix: check the tar error above — the archive may be corrupt or
           truncated."; }
            # A tarball made by db-backup.sh -t contains exactly one top-level
            # directory. Anything else is not one of ours; refuse rather than
            # guess which of several directories is the datadir.
            set -- "$untarred"/*
            if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
                rm -rf "$untarred"
                die "error: $SRC does not contain exactly one top-level directory, so it
      is not an archive db-backup.sh -t wrote.
      Fix: unpack it yourself and pass the prepared directory instead."
            fi
            SRC=$1 ;;
        *) die "error: $SRC is a file, not a directory, and not a .tgz.
      Fix: pass a prepared xtrabackup directory, or a .tgz written by
           'db-backup.sh -t'." ;;
    esac
fi

[ -d "$SRC" ] || { rm -rf "$untarred" 2>/dev/null; die "error: not a directory: $SRC
      Fix: check the path for a typo, or pass a prepared xtrabackup
           directory, or a .tgz written by 'db-backup.sh -t'."; }

# Validate the source BEFORE anything is destroyed. The container command
# below runs `rm -rf /var/lib/mysql/*` first and only then lets
# `xtrabackup --copy-back` look at /restore, so a wrong or unprepared
# directory took the datadir with it before the error was even printed.
#
# xtrabackup_checkpoints is the marker, and this is measured against
# percona/percona-xtrabackup:8.0 (xtrabackup 8.0.35-36), the image this script
# runs, not inferred:
#   * `xtrabackup --backup` writes it with `backup_type = full-backuped`;
#     `xtrabackup --prepare` rewrites the same line to `full-prepared`.
#   * `--copy-back` reads ./xtrabackup_checkpoints first of all.
#   * Given `full-backuped` OR `log-applied` (what `--prepare --apply-log-only`
#     leaves), `--copy-back` refuses and copies nothing. Given `full-prepared`
#     it restores.
# So `full-prepared` is exactly xtrabackup's own accept/reject boundary: this
# rejects nothing --copy-back would have accepted, it only moves the refusal to
# before the wipe instead of after it.
checkpoints="$SRC/xtrabackup_checkpoints"
[ -f "$checkpoints" ] || { rm -rf "$untarred" 2>/dev/null; die "error: $ORIG_SRC has no xtrabackup_checkpoints, so it is not an xtrabackup
      backup directory. Nothing was changed.
      Fix: pass a directory db-backup.sh produced, or a .tgz written by
           'db-backup.sh -t'."; }

backup_type=$(sed -n 's/^backup_type[[:space:]]*=[[:space:]]*//p' "$checkpoints" | tr -d '[:space:]')
if [ "$backup_type" != "full-prepared" ]; then
    rm -rf "$untarred" 2>/dev/null
    die "error: the backup at $ORIG_SRC is not prepared (backup_type =
      '${backup_type:-<unreadable>}'; 'full-prepared' is required).
      xtrabackup --copy-back would refuse it, but only after this script had
      already emptied the data directory. Nothing was changed.
      Fix: run 'xtrabackup --prepare --target-dir=$SRC' first."
fi

printf "Replace this stack's ENTIRE MySQL data directory from %s? [y/N] " "$ORIG_SRC"
read -r answer || answer=""
case "$answer" in
    y|Y|yes|YES) ;;
    *) rm -rf "$untarred" 2>/dev/null; die "cancelled — nothing was changed." ;;
esac

# Signal handling, ported from the cold-tar db-restore.sh this replaces. The
# xtrabackup path had NO traps at all: an interrupt during the container
# command below left a half-wiped datadir, a stopped database, and no message.
#
# INT, TERM and HUP are trapped explicitly because an EXIT trap alone does not
# fire on a signal in every shell this might run under — HUP specifically
# because a dropped SSH session sends the foreground process group SIGHUP, and
# a restore is exactly the kind of command an operator runs over SSH.
#
# A trap that only runs `cleanup` and returns does NOT stop the script: the
# shell resumes at the next statement (measured — dash, bash and busybox sh all
# do), so a signal during `compose stop database` would restart the database
# via the trap and then carry on into the wipe. Each handler runs `cleanup`,
# restores the signal's default action, then re-raises it against this process.
# `cleanup` stays idempotent (guarded by $restarted) because the re-raise can
# also trigger the EXIT trap.
#
# The source of truth for "was the datadir touched?" lives INSIDE the
# container, not in a host-side flag. $sentinel_dir is bind-mounted at /state;
# the container touches /state/wiping immediately before `rm -rf` and removes
# it immediately after `--copy-back` succeeds. A host-side flag tracked the
# host's INTENT to run the wipe instead: a `docker run` that failed before
# touching anything still set it (reporting a false INCONSISTENT), and a
# signal landing between a successful run returning and the host clearing the
# flag did the same. The file's state on disk IS the datadir's state.
#
# The `touch` is a PRECONDITION of the wipe, not an annotation of it, which is
# why it is `|| exit 90` and not `;`. If the sentinel cannot be written this
# script has no way left to report a half-restored datadir — so it must not
# create one. Left unchecked, a failed touch fell through to the `rm -rf`, and
# cleanup() then read the missing file as "nothing was touched" and restarted
# MySQL on a datadir that had just been emptied, silently. Reachable whenever
# the bind mount is not writable: SELinux enforcing without a :z/:Z label, or a
# full or read-only TMPDIR. 90 does not collide with tar's 1/2 or docker's
# 125-127.
restarted=0
sentinel_dir="${TMPDIR:-/tmp}/db-restore-state.$$"
mkdir "$sentinel_dir" || die "error: could not create a temp directory at $sentinel_dir to
      track restore progress.
      Fix: check that ${TMPDIR:-/tmp} exists and is writable."

cleanup() {
    if [ "$restarted" -eq 0 ]; then
        restarted=1
        if [ -e "$sentinel_dir/wiping" ]; then
            printf '%s\n' "==> interrupted mid-restore: this stack's MySQL datadir is now
      INCONSISTENT — the previous contents were removed and the backup was
      only partially copied back. The database has been left STOPPED on
      purpose: starting MySQL on a half-written datadir risks it coming up on
      corrupt files instead of failing loudly.
      Fix: re-run './eyened restore $ORIG_SRC' to finish the restore before
      using this database again." >&2
        else
            echo "==> interrupted or failed: restarting the database" >&2
            compose start database ||
                echo "error: could not restart the database — start it by hand: (cd $DEPLOY_DIR && $COMPOSE_BIN start database)" >&2
        fi
    fi
    rm -rf "$sentinel_dir" "$untarred" 2>/dev/null
}
trap cleanup EXIT
trap 'cleanup; trap - INT; kill -INT $$' INT
trap 'cleanup; trap - TERM; kill -TERM $$' TERM
trap 'cleanup; trap - HUP; kill -HUP $$' HUP

echo "==> stopping the database"
compose stop database

compose --profile backup run --rm --user 0:0 \
    -v "$SRC:/restore" \
    -v "$sentinel_dir:/state" \
    --entrypoint sh \
    xtrabackup -c 'set -eu
touch /state/wiping || exit 90
rm -rf /var/lib/mysql/* /var/lib/mysql/.[!.]* /var/lib/mysql/..?*
xtrabackup --copy-back --target-dir=/restore --datadir=/var/lib/mysql
chown -R 999:999 /var/lib/mysql
rm -f /state/wiping'

echo "==> starting the database"
compose start database
restarted=1
trap - EXIT INT TERM HUP
rm -rf "$sentinel_dir" "$untarred" 2>/dev/null
echo "restored from $ORIG_SRC"
