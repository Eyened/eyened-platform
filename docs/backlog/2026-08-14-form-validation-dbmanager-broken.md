# `form_validation` cannot be imported — `DBManager` does not exist

**Found:** 2026-08-14, while writing the coverage omit guard.
**Status:** recorded, not repaired.

`orm/eyened_orm/form_validation/validator.py:10` does `from ..db import DBManager`.
No `DBManager` exists anywhere in the repo except the two `form_validation` files
that reference it, so all three modules in the package raise
`ImportError: cannot import name 'DBManager' from 'eyened_orm.db'` — 189 statements
that cannot be imported, let alone tested.

This is a live crash, not dead code: `orm/eyened_orm/cli.py:256` imports the package
lazily inside a command body, so the failure surfaces only when that command runs.

The modules are **not** omitted from coverage. They fail the omission criterion —
which requires an absent third-party package, not broken repo code — and are instead
grandfathered in `KNOWN_UNIMPORTABLE` in `server/tests/test_coverage_omissions.py`.
That set only shrinks, so repairing or deleting them forces the entry out.

Repair means deciding whether `DBManager` should exist or whether the package should
be deleted. Neither is in scope for the coverage gate.
