#!/bin/sh
set -e
cd /app/client

# node_modules is a named volume: it seeds from the image only on first
# creation, so a lockfile bump would otherwise leave stale dependencies.
# `npm ci` below removes node_modules before it can fail, so a boot offline
# after a lockfile bump leaves none until the registry is reachable again.
stamp=node_modules/.lock-stamp

# NOT `md5sum ... | cut ...`: a pipeline reports only cut's status and cut
# succeeds on empty input, so an unreadable lockfile would leave $want empty
# with a zero status and compare equal to an empty $have.
want=$(md5sum package-lock.json) || {
  echo "entrypoint-client: cannot hash package-lock.json — refusing to start on unverified modules" >&2
  exit 1
}
want=${want%% *}
have=$(cat "$stamp" 2>/dev/null || true)

# The marker test catches only a removed npm marker beside a surviving stamp;
# an emptied node_modules takes the stamp with it and fires the hash compare.
if [ ! -f node_modules/.package-lock.json ] || [ "$want" != "$have" ]; then
  echo "entrypoint-client: dependencies do not match package-lock.json, installing"
  npm ci
  printf '%s\n' "$want" > "$stamp"
fi

exec npm exec vite -- --host 0.0.0.0 --port 5173 dev
