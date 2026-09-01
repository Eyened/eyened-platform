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
from sqlalchemy import inspect, select
from eyened_orm import Database, StorageBackend

configured = set(json.loads(os.environ.get("EYENED_STORAGE_MOUNTS") or "{}"))

db = Database()
# "You never bootstrapped this database" is an ordinary operator state, not a
# bug, and without this guard it arrived as a ~60-line pymysql/SQLAlchemy
# traceback ending in (1146, "Table ... StorageBackend does not exist") plus a
# bare "make: *** Error 1". The machinery was right and the message sent the
# reader nowhere. It is reachable by a completely normal route: a bare
# "docker compose up -d" brings the stack up WITHOUT creating the schema,
# because bootstrap.sh is only ever run by ./install.sh and "make up". Every
# container then reports healthy on an empty database.
#
# This exits non-zero on purpose. Nothing was compared, so reporting "they
# agree" would be a check that cannot fail — which is precisely how an empty
# schema went unnoticed for 43 minutes of a verification run.
#
# NOTE: this whole program is a single-quoted argument to sh -c, so it must
# not contain an apostrophe or any other single quote anywhere, comments
# included — one would end the shell string and hand the rest of this file to
# sh as commands.
if not inspect(db.engine).has_table(StorageBackend.__tablename__):
    raise SystemExit(
        f"error: this database has no {StorageBackend.__tablename__} table, so there is\n"
        "      nothing to compare storage-mounts.conf against — the schema has never\n"
        "      been created here.\n"
        "      Fix: run ./install.sh (production stack) or make up (developer stack).\n"
        "           Both run bootstrap.sh, which creates the schema; a bare\n"
        "           docker compose up -d does not."
    )

with db.get_session() as session:
    rows = set(session.execute(select(StorageBackend.Key)).scalars())

for key in sorted(configured - rows):
    print(f"configured but no StorageBackend row: {key}")
for key in sorted(rows - configured):
    print(f"StorageBackend row but not configured: {key}")
if configured == rows:
    print(f"storage-mounts.conf and StorageBackend rows agree ({len(rows)} key(s)).")
'
