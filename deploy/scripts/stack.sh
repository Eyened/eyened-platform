#!/bin/sh
# Bring the stack up. One implementation, three modes:
#
#   dev      developer stack — hot reload, source mounted, bundled database
#   install  client install  — production stack on a database this stack owns
#   prod     site deployment — production stack on an EXTERNAL database
#
# Every mode runs the same five steps in the same order; a mode only decides
# which layer list is recorded, whether 'local-db' is expected, and whether the
# first-run bootstrap applies. Keeping that in one file is the point: the
# startup order is fixed in one place or it drifts in three.
set -eu

MODE=${1:-}
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"

case "$MODE" in
    dev|install|prod) ;;
    *) die "usage: stack.sh dev|install|prod" ;;
esac

# Before anything is read or written, including doctor: under sudo every file
# this run creates lands root-owned, and deploy/.env at mode 600 is then
# unreadable to the invoking user's own later `docker compose`. Refusing costs
# five lines; compensating for it afterwards cost fifty and had to be repeated
# at every write path.
refuse_sudo

# doctor takes dev|client: 'install' and 'prod' both build the client stack.
case "$MODE" in
    dev) doctor_mode=dev ;;
    *)   doctor_mode=client ;;
esac

echo "==> checking this machine"
"$DEPLOY_DIR/scripts/doctor.sh" "$doctor_mode"

resolve_compose

case "$MODE" in
    dev)     write_env dev ;;
    install) write_env client ;;
    prod)
        # A site deployment is never bootstrapped from a template: the .env
        # must already point at the external database for THIS site.
        [ -f "$DEPLOY_DIR/.env" ] || die "error: deploy/.env does not exist.
      A site deployment needs it configured for THIS site — at minimum
      EYENED_DATABASE_* pointing at the external database, and
      COMPOSE_PROFILES without 'local-db'.
      Fix: cp deploy/.env.example deploy/.env and edit it."

        case "$(env_get COMPOSE_PROFILES)" in
            *local-db*)
                die "error: COMPOSE_PROFILES still contains 'local-db', which starts the
      bundled MySQL. 'make prod' is for a database this stack does not own.
      Fix: remove 'local-db' from COMPOSE_PROFILES in deploy/.env, or run
           ./install.sh if you do want the bundled database." ;;
        esac
        # Nothing writes .env in this branch. A site's .env is hand-configured
        # by definition — the refusal above sends the operator to edit it
        # themselves — so rewriting COMPOSE_FILE underneath them was never
        # this mode's business. doctor has already refused a COMPOSE_FILE that
        # does not name the client stack.
        ;;
esac

# .env and storage-mounts.conf have independent lifetimes, so this is not part
# of write_env: .env can be perfectly good while storage-mounts.conf is absent
# (deleted, or a checkout that predates it), and write_env returns early in
# exactly that case. gen-storage.sh dies on a missing storage-mounts.conf, and
# all three modes reach it — including prod, which never had this before.
ensure_storage_mounts
"$DEPLOY_DIR/scripts/gen-storage.sh"

echo "==> building images and starting the stack"
[ "$MODE" = dev ] || echo "    (the first run builds everything from source and takes a while)"
compose up -d --build

# Not in prod: bootstrap declines an external database anyway, and a site's
# schema is not this script's to create. See deploy/README.md on migrations.
[ "$MODE" = prod ] || "$DEPLOY_DIR/scripts/bootstrap.sh"

print_day2
