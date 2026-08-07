#!/bin/sh
# Report disagreement between configured mounts and StorageBackend rows.
#
# Deliberately NOT part of ./install.sh or make up: generation has to work
# before any database exists, which is exactly the state a first run is in.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$REPO_ROOT/deploy/scripts/lib.sh"
resolve_compose

compose exec -T server python -c '
import json, os
from sqlalchemy import select
from eyened_orm import Database, StorageBackend

configured = set(json.loads(os.environ.get("EYENED_STORAGE_MOUNTS") or "{}"))
with Database().get_session() as session:
    rows = set(session.execute(select(StorageBackend.Key)).scalars())

for key in sorted(configured - rows):
    print(f"configured but no StorageBackend row: {key}")
for key in sorted(rows - configured):
    print(f"StorageBackend row but not configured: {key}")
if configured == rows:
    print(f"storage-mounts.conf and StorageBackend rows agree ({len(rows)} key(s)).")
'
