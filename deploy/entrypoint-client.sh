#!/bin/sh
set -e
cd /app/client

# node_modules is a NAMED volume, so it seeds from the image only on first
# creation. This script used to reinstall only when npm's own marker file
# (node_modules/.package-lock.json) was missing — that is, only when the
# directory had never been installed into at all. It left a developer on stale
# dependencies after a package-lock.json bump, silently, until someone thought
# to run `docker compose down -v`. It now also compares a hash of the mounted
# lockfile against the stamp written when these modules were installed.
stamp=node_modules/.lock-stamp

# NOT `md5sum ... | cut ...`: a pipeline reports only the last command's exit
# status, and `cut` succeeds on empty input — so an unreadable or missing
# lockfile would leave $want empty with a ZERO status, `set -e` would not fire,
# and an empty $have would then compare EQUAL. The script would skip the
# install and start vite on unverified modules: precisely the silent staleness
# this check exists to prevent, reached from the other direction.
want=$(md5sum package-lock.json) || {
  echo "entrypoint-client: cannot hash package-lock.json — refusing to start on unverified modules" >&2
  exit 1
}
want=${want%% *}
have=$(cat "$stamp" 2>/dev/null || true)

# The marker test stays as a second condition rather than being replaced by the
# stamp comparison: it is the only thing that catches a node_modules emptied or
# corrupted by hand while a matching stamp survived. A missing stamp alone is
# already covered, since $have is then empty and cannot equal a real hash.
if [ ! -f node_modules/.package-lock.json ] || [ "$want" != "$have" ]; then
  echo "entrypoint-client: dependencies do not match package-lock.json, installing"
  npm ci
  printf '%s\n' "$want" > "$stamp"
fi

exec npm exec vite -- --host 0.0.0.0 --port 5173 dev
