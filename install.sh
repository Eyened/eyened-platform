#!/bin/sh
# The client entry point for the Eyened platform.
#
#   git clone https://github.com/Eyened/eyened-platform.git
#   cd eyened-platform
#   ./install.sh
#
# Installs the PRODUCTION stack (gunicorn, built client, no source mounts) on a
# database this stack owns. Docker is the only prerequisite. Re-running it on
# an installed stack is safe: it rebuilds and re-bootstraps.
set -eu
exec "$(cd "$(dirname "$0")" && pwd)/deploy/scripts/stack.sh" install
