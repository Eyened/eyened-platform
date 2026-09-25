# CI, tooling and code health

### Bump `python-multipart`
- **Status:** open
- **Source:** Dependabot, re-counted 2026-08-24
- **Problem:** `server/requirements.txt` pins `python-multipart==0.0.20`; 14 alerts (7 advisories counted twice via `test-requirements.txt`), including 3 high, all fixed by ≤ 0.0.31. Reachable on every form/upload endpoint.
- **Fix:** bump to the current latest in its own small PR.

### Clear the npm Dependabot alerts in `client/` and `docs/`
- **Status:** open
- **Source:** Dependabot, re-counted 2026-08-24 (111 npm: 62 docs, 49 client)
- **Problem:** mostly build/generator tooling (`brace-expansion`, `js-yaml`, `fast-uri`, `vite`, `tar-fs`, `postcss`, `nanoid`, `astro`, ...); accumulating ~1/day.
- **Fix:** `npm audit fix` in `client/`, then `docs/`, one PR each; manual major bumps only where needed. Consider Dependabot version-update PRs.

### Add a backend ruff lint + format gate
- **Status:** open
- **Source:** descoped from #118, 2026-07-16
- **Problem:** no `[tool.ruff]`, no lint job in `server-ci.yml`. 2026-07-16 baseline (stale; re-measure): 125 `ruff check` errors incl. 17 F403, 11 F821; 121 files unformatted.
- **Fix:** one isolated `ruff format server orm` PR, then ratcheted `select` per rule; review F403/F821 individually (possible real bugs), no bulk `--fix`.

### Make CI checks required on `main`/`development` (coverage Phase C)
- **Status:** open, by design after several weeks of advisory runs
- **Source:** PR #208 final review, 2026-08-18
- **Problem:** ruleset "Protect main and dev branch" (id 18935463) gates on review only; no `required_status_checks`. Two blind spots make a required coverage gate under-measure: narrowing `[tool.coverage.run] source` below `orm` collides `db.py` paths; a directory without `__init__.py` (e.g. `orm/migrations/alembic/versions_archive/`) is invisible.
- **Fix:** guard both blind spots in `server/tests/test_coverage_omissions.py`, then add `required_status_checks` (`Server CI / schema-sync` is the strongest candidate). Needs repo admin rights (unconfirmed).

### Repair or delete `eyened_orm.form_validation`
- **Status:** open
- **Source:** coverage omit guard, 2026-08-14
- **Problem:** `form_validation/validator.py` imports `DBManager` from `..db`, which does not exist, so the package cannot import; the lazy import in the `cli.py` command crashes when run. `notebooks/orm_demo.ipynb` uses `DBManager` too.
- **Fix:** decide whether `DBManager` should exist or delete the package (and fix the notebook); then remove the entry from `KNOWN_UNIMPORTABLE` in `server/tests/test_coverage_omissions.py`.
