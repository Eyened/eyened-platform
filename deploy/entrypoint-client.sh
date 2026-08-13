#!/bin/sh
set -e
cd /app/client

# node_modules is a NAMED volume, so it seeds from the image only on first
# creation. Checking merely that it is non-empty — which this script used to do
# — leaves a developer on stale dependencies after a package-lock.json bump,
# silently, until someone thinks to run `docker compose down -v`. Compare a
# hash of the mounted lockfile against the stamp written when these modules
# were installed.
stamp=node_modules/.lock-stamp
want=$(md5sum package-lock.json | cut -d' ' -f1)
have=$(cat "$stamp" 2>/dev/null || true)

if [ ! -f node_modules/.package-lock.json ] || [ "$want" != "$have" ]; then
  echo "entrypoint-client: dependencies do not match package-lock.json, installing"
  npm ci                                    # <- Step 2's chosen command
  printf '%s\n' "$want" > "$stamp"
fi

exec npm exec vite -- --host 0.0.0.0 --port 5173 dev
