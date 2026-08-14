#!/bin/sh
# Stop the stack and DELETE its volumes — database and platform storage.
#
# Refuses outright when this stack is attached to storage or a database it
# does not own, so it cannot be aimed at shared or production data.
#
# These guards read deploy/.env via env_get. Compose also honours the SHELL
# environment, which overrides .env — so running this with, say,
# COMPOSE_PROFILES set in the calling shell diverges from what the guard
# actually inspected. Unset any of PLATFORM_STORAGE_PATH, DB_DATA_PATH,
# COMPOSE_PROFILES or EYENED_DATABASE_HOST in your shell before relying on
# these checks.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

# env_get returns empty BOTH for a key that is absent and for a .env that does
# not exist at all, and the two are not the same thing — the same conflation
# bootstrap.sh refuses to guess through. Without this check every guard below
# reads empty, and the COMPOSE_PROFILES one fires first: a machine that has
# never been installed is told "this stack uses an external database", a
# diagnosis of a configuration that does not exist. Name the real problem.
[ -f "$DEPLOY_DIR/.env" ] || die "refusing: $DEPLOY_DIR/.env does not exist, so there is no stack here to
      reset — and nothing to check ownership against either.
      Fix: run ./install.sh or 'make up' first if you meant to create one."

platform_storage=$(env_get PLATFORM_STORAGE_PATH)
[ -z "$platform_storage" ] || die "refusing: PLATFORM_STORAGE_PATH is set to $platform_storage.
      This stack is attached to storage it does not own. Unset it in
      deploy/.env if you really mean to reset a stack with its own volume."

# The exact analogue for the database. compose.yaml mounts
# ${DB_DATA_PATH:-db_data} at /var/lib/mysql: unset, that is this stack's own
# named volume and `down -v` deletes it; SET, it is a bind mount on durable
# storage and the db_data volume does not exist at all, so `down -v` removes
# nothing of the database. Measured with DB_DATA_PATH=/srv/eyened-durable-db:
# `compose config` lists platform_storage and no db_data whatsoever.
#
# It UNDER-deletes rather than over-deletes, so this is not data loss — but
# reset then cannot do what its name says, and the operator's next
# ./install.sh reports "the database already has N tables — it will not be
# migrated" and creates no admin, with nothing along the way having said the
# database survived. deploy/README.md already documents this as the contract.
db_data_path=$(env_get DB_DATA_PATH)
[ -z "$db_data_path" ] || die "refusing: DB_DATA_PATH is set to $db_data_path.
      /var/lib/mysql is then a bind mount on storage this stack does not own,
      so 'down -v' would leave the entire database intact — reset cannot do
      what its name says. Unset it in deploy/.env if you really mean to reset
      a stack with its own volume; delete that directory by hand if you
      really mean to destroy the durable copy."

case "$(env_get COMPOSE_PROFILES)" in
    *local-db*) ;;
    *) die "refusing: this stack uses an external database (no 'local-db' profile).
      Reset only removes volumes this stack owns; the external database would
      be untouched, which is not what 'reset' implies." ;;
esac

db_host=$(env_get EYENED_DATABASE_HOST)
case "${db_host:-database}" in
    database) ;;
    *) die "refusing: EYENED_DATABASE_HOST is '$db_host', not the bundled 'database'.
      Point it back at the bundled database, or use the tools of whatever
      server it names." ;;
esac

project=$(env_get COMPOSE_PROJECT_NAME)
[ -n "$project" ] || die "refusing: COMPOSE_PROJECT_NAME is not set in deploy/.env.
      Reset needs a project name to confirm against; an empty one would make
      an empty answer (a bare Enter) match. Set COMPOSE_PROJECT_NAME in
      deploy/.env and re-run."

# Ask compose which volumes it would actually remove, rather than rebuilding
# them as "${project}_db_data". db-snapshot.sh already documents why the
# string-built form is wrong — compose normalises the project name, so the
# reconstruction can name something that does not exist — and here it was
# wrong about WHICH volumes exist too: it listed db_data unconditionally, even
# in the DB_DATA_PATH case above where there is no such volume at all.
#
# `config` resolves the same .env AND the same shell environment compose
# itself does, so this list cannot disagree with what `down -v` will remove,
# including in the shell-override case the header comment warns about.
#
# The parse is anchored on compose's own two-space JSON indentation: the
# top-level "volumes" object at indent 2, each volume's resolved "name" at
# indent 6. Nothing is invented if that ever stops matching — the list comes
# back empty and the check below refuses rather than printing a guess.
volumes=$(compose config --format json 2>/dev/null | awk '
    /^  "volumes": \{$/ { in_v = 1; next }
    in_v && /^  \}/     { in_v = 0 }
    in_v && /^      "name": "/ {
        _n = $0
        sub(/^      "name": "/, "", _n)
        sub(/",?$/, "", _n)
        print _n
    }
') || volumes=""

[ -n "$volumes" ] || die "refusing: could not read this stack's volume list from
      '$COMPOSE_BIN config'. Reset will not name volumes it has not confirmed,
      and will not run 'down -v' blind.
      Fix: run '(cd $DEPLOY_DIR && $COMPOSE_BIN config)' and fix what it
           reports."

cat <<EOF
This will stop the '$project' stack and permanently delete its volumes:

EOF
# The annotations are keyed off the resolved name's suffix, not rebuilt
# alongside it, so a volume compose reports and this script does not recognise
# is still listed rather than silently dropped from a destructive prompt.
printf '%s\n' "$volumes" | while IFS= read -r _vol; do
    case "$_vol" in
        *_db_data)          printf '  %-30s the entire database\n' "$_vol" ;;
        *_platform_storage) printf '  %-30s thumbnails and segmentations.zarr\n' "$_vol" ;;
        *)                  printf '  %s\n' "$_vol" ;;
    esac
done
echo

printf "Type the project name (%s) to confirm: " "$project"
read -r answer
[ "$answer" = "$project" ] || die "cancelled — nothing was removed."

compose down -v
echo "removed. Run ./install.sh or make up to start over."
