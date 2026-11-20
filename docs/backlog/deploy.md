# Deploy

### Decide what `init` does on a schema behind head
- **Status:** open (design decision)
- **Source:** PR #202 whole-PR review, 2026-09-21
- **Problem:** with auto-migrate off, `eorm bootstrap` (`orm/eyened_orm/commands/bootstrap.py`) reports pending migrations and exits 0, which satisfies `server`'s `service_completed_successfully` gate, so `up` serves new code against the old schema and `compose ps` says healthy.
- **Fix:** pick one: (A) exit non-zero naming the migrate command; (B) non-zero only when `EYENED_AUTO_MIGRATE` is unset; (C) keep the exit code and have `/health` report a schema behind head.
- **Note:** A turns a forgotten migrate step into an outage (compose has already stopped the old `server`); B needs a third state, but `deploy/compose.yaml` always sets the variable.

### Build and smoke-test the images CI skips
- **Status:** open
- **Source:** deploy slim-down review, 2026-09-18
- **Problem:** `.github/workflows/deploy-validate.yml` builds only the prod `server` and `fileserver` images; the dev `client` image (which depends on the `.dockerignore` re-include of `deploy/entrypoint-client.sh`) and the worker images are never built. The smoke job asserts nothing about seeding.
- **Fix:** build the dev and worker images in CI; assert `SELECT COUNT(*) FROM FormSchema` > 0 in the smoke job.

### Run the upgrade path end to end once
- **Status:** open
- **Source:** deploy slim-down review, 2026-09-18
- **Problem:** only a fresh database and an idempotent re-run were shown; never a rebuild with `init` recreated on the new image migrating a schema behind head. If compose did not recreate `init`, the old image would exit 0 without migrating.
- **Fix:** run it once by hand and assert on `alembic_version`, not container status.

### Tidy the slim-down's stale messages
- **Status:** open
- **Source:** deploy slim-down review, 2026-09-18
- **Problem:** the release notes have no breaking-change bullet saying `up` no longer migrates (`EYENED_AUTO_MIGRATE` now defaults to `false`), and `release_notes.mdx:119`'s "makes an unattended first-run bootstrap possible" is stale (`eorm bootstrap` calls `upgrade_to_head` directly). `bootstrap.py` prints "Empty database" whenever `alembic_version` is missing, even when tables exist.
- **Fix:** add the bullet, drop the clause, and word the log line by what `bootstrap.py` actually checked.

### Move `orm` (and maybe `server`) to `pyproject.toml`
- **Status:** open
- **Source:** PR #202 review (whyscream), 2026-09-09
- **Problem:** `orm/setup.py` means `pip install -e` needs the source present, so every `orm` edit reinstalls every dependency in the image builds.
- **Fix:** a `[project]` table in `orm/pyproject.toml`, decide whether `server` becomes a package, then install from manifests before copying source (e.g. `uv sync --no-install-project`). Touches `deploy/Dockerfile.server`, the four `worker/Dockerfile.*`, both `server-ci.yml` jobs, the dev venv and the `eorm` entry point.

### Resolve the three GPU worker images in one pip install
- **Status:** open, needs GPU image rebuilds to verify
- **Source:** PR #202 review (whyscream), 2026-09-09
- **Problem:** `worker/Dockerfile.cfi-amd`, `Dockerfile.inference` and `Dockerfile.layersegmentation` install `server/requirements.txt`, `-e orm` and their model packages in separate `RUN pip install` steps; pip exits 0 when a later step breaks an earlier pin (measured 2026-09-15: `tifffile` vs `numpy 2.0.0`).
- **Fix:** one install per image, then `pip check` in the built image.
