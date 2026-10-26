# `alembic check` lists every table on `lower_case_table_names=1` servers

- **Source:** v2026.09.1 hotfix, 2026-10-26.
- **Status:** open

**What:** Normalise table names in `orm/migrations/alembic/env.py` so `alembic check` compares the models with a lowercase server's schema.

**Why:** On those servers MySQL stores every table name in lowercase, so `alembic check` lists every table. The upgrade guide tells operators to ignore it and read `alembic current`, which leaves those sites without a drift check.
