#!/bin/sh
# Run compose with whichever binary this host has, from deploy/ where .env and
# the layer files live:
#
#   deploy/scripts/dc.sh logs -f
#
# This exists so the Makefile never has to know the binary. The alternative —
# a script that PRINTS the name into a make variable — evaluates on every make
# invocation including `make help`, and leaves the variable EMPTY when docker
# is missing, so `make down` silently degrades into `cd deploy && down`.
set -eu
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose
compose "$@"
