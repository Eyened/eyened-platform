# PR-Triggered Test CI — Design (parked)

**Date:** 2026-07-06
**Status:** Approved design, implementation deferred. Only the *local test-runner
enablement* subset (pinned test deps + fixed pytest config) is being executed now,
folded into the RBAC Step 1 plan
(`docs/superpowers/plans/2026-07-03-repository-service-layer-step1.md`, Task 0).
The GitHub Actions workflow and everything CI-facing described below ships as its
own separate PR.

**Goal:** Make the existing test suite installable and runnable with a single
command, wire it into GitHub Actions so it runs on every pull request into `main`
or `development`, and keep the whole thing trivially liftable to any cloud runner
later.

---

## Current-setup analysis

- **Hosting / CI:** Repo is on GitHub (`Eyened/eyened-platform`). The only workflow
  is `.github/workflows/deploy.yml` — it builds the Astro docs and deploys to
  GitHub Pages on push to `main` and manual dispatch. **There is no test job and no
  PR trigger today.**
- **The test suite is real:** ~24 test files across `server/tests/` and
  `orm/eyened_orm/**/tests/`. They use an **in-memory SQLite** fixture
  (`orm/eyened_orm/utils/sqlite_testdb.py`, with MySQL→SQLite type shims) and dummy
  DB env vars set by `server/tests/conftest.py::pytest_configure`. **The suite needs
  no live MySQL**, which keeps CI simple.
- **Dependency declaration is fragmented and runtime-only:**
  - `server/requirements.txt` — server runtime deps; **no pytest**, and does **not**
    reference orm.
  - `orm/setup.py` — setuptools `install_requires` (SQLAlchemy, numpy, …); the only
    source of the ORM's runtime deps. **No pytest.**
  - `server/test-requirements.txt` — exists, one unpinned line: `pytest`.
  - Root `pyproject.toml` — holds only pytest config, under the **wrong header**
    (`[tool.pytest]` instead of `[tool.pytest.ini_options]`), so `testpaths` /
    `pythonpath` are **silently ignored**; and `minversion = "9.0"` is
    **unsatisfiable** (pytest is 8.x).
- **pytest is installed nowhere** — not `dev/.venv`, not the `server` container.
- **`eyened_orm` is importable** in `dev/.venv` only because it is installed
  **editable** (`pip install -e ./orm`); a fresh interpreter from the repo root gets
  `ModuleNotFoundError`. CI must reproduce this.

## Requirements

1. Run the test suite automatically when a PR is created (into `main` / `development`).
2. Keep it easy to progress to cloud CI/CD later.
3. Symmetry with local development — the same command that CI runs should be what a
   developer runs locally, so there is no "works on my machine" drift.

## Decision: Approach A — native runner (pip + pytest)

Tests run **natively** on the runner: check out, `pip install` deps + pytest, run
`pytest`. Chosen over Approach B (build the Docker image and `docker run … pytest`)
because:

- **Local/CI symmetry is A's core strength.** Both sides install from one shared
  deps file and run bare `pytest`; the only difference is the interpreter *path*
  (`dev/.venv/bin/` locally vs. the runner's fresh venv), not the environment.
- The suite is **pure in-memory SQLite** with no service dependencies, so B's
  prod-parity benefit is small today.
- **Cloud-lift is trivial:** any future cloud runner is "same installs + `pytest` on
  another machine." B (Docker) is the better choice only once tests exercise the real
  MySQL/container runtime — revisit then.

## Design

### 1. Dependency wiring (single source of truth)

`server/test-requirements.txt` becomes:

```
-r requirements.txt
pytest==8.*
```

- `-r requirements.txt` chains the server runtime deps so one
  `pip install -r server/test-requirements.txt` installs everything.
- `pytest==8.*` pins the tool so a new pytest release can't spontaneously break the
  build.

orm stays a **separate editable install** — it is the only source of SQLAlchemy et
al. and must be importable at collection time:

```
pip install -e ./orm
pip install -r server/test-requirements.txt
```

These two commands are identical locally and in CI.

### 2. Fix the pytest config

Root `pyproject.toml`: rename `[tool.pytest]` → `[tool.pytest.ini_options]` and drop
`minversion = "9.0"`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = [
    "server",
    "orm",
]
```

Now `pythonpath = ["."]` puts the repo root on `sys.path` so `import server.*`
resolves at collection, and bare `pytest` auto-discovers both `server` and `orm`.

### 3. CI workflow — new `.github/workflows/tests.yml`

Separate from `deploy.yml`:

```yaml
name: Tests
on:
  pull_request:
    branches: [main, development]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: |
          python -m pip install --upgrade pip
          pip install -e ./orm
          pip install -r server/test-requirements.txt
      - run: pytest
```

- **No MySQL service** — the suite is in-memory SQLite.
- **No env vars needed** — `server/tests/conftest.py::pytest_configure` sets the
  dummy DB creds itself.

### 4. Local unblock

Run the same two installs into `dev/.venv` so `dev/.venv/bin/pytest` works. (This is
the subset executed now, as Task 0 of the RBAC Step 1 plan.)

## Prerequisite / risk

**Before the gate is trustworthy, the *existing* suite must be green.** Nobody has
run it here (no pytest). Implementation installs locally and runs the full suite
first; if anything is already red, surface and decide before flipping on a CI gate
that would block every PR.

## Sequencing

- **Now (in the RBAC plan, Task 0):** the local test-runner enablement — refine
  `server/test-requirements.txt`, fix `pyproject.toml`, install into `dev/.venv`,
  confirm the baseline suite is green.
- **Separate PR (this spec's remaining scope):** add `.github/workflows/tests.yml`
  on the `pull_request` trigger. Branch off `development`.

## Out of scope

- The `httpxyz` dependency audit — `server/requirements.txt` pins `httpxyz>=0.31.2`,
  a name/version that shadows the well-known `httpx` (a typosquat smell). It resolves
  on PyPI and does not break CI, but warrants a separate look.
- Migrating dependency management to `pyproject`.
- A Docker-based test stage (Approach B).
- Post-merge `push` triggers and cloud CD.
