#!/bin/sh
# Stop the stack and DELETE its volumes — database and platform storage.
#
# Refuses outright when this stack is attached to storage or a database it
# does not own, so it cannot be aimed at shared or production data.
#
# These guards read deploy/.env via env_get. Compose also honours the SHELL
# environment, which overrides .env — so running this with, say,
# COMPOSE_PROFILES set in the calling shell diverges from what the guard
# actually inspected. Unset any of PLATFORM_STORAGE_PATH, COMPOSE_PROFILES or
# EYENED_DATABASE_HOST in your shell before relying on these checks.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

platform_storage=$(env_get PLATFORM_STORAGE_PATH)
[ -z "$platform_storage" ] || die "refusing: PLATFORM_STORAGE_PATH is set to $platform_storage.
      This stack is attached to storage it does not own. Unset it in
      deploy/.env if you really mean to reset a stack with its own volume."

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

cat <<EOF
This will stop the '$project' stack and permanently delete its volumes:

  ${project}_db_data           the entire database
  ${project}_platform_storage  thumbnails and segmentations.zarr

EOF
printf "Type the project name (%s) to confirm: " "$project"
read -r answer
[ "$answer" = "$project" ] || die "cancelled — nothing was removed."

compose down -v
echo "removed. Run ./install.sh or make up to start over."
