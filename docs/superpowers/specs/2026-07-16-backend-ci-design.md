# Backend CI (tests) — Design

**Date:** 2026-07-16
**Issue:** #118 — run backend tests in GitHub Actions
**Base branch:** `development`
**Status:** Approved design; implementation pending.

## Goal

Add a GitHub Actions gate that runs the backend **test suite** on every pull request
into `development`/`main` and on every push to those branches, using the same command a
developer runs locally — and bring `client-ci.yml` in line with the same trigger and
concurrency policy. **Python linting (ruff) is deferred** to a follow-up (see
`docs/backlog/2026-07-16-backend-ruff-lint-followup.md`); §"Deferred: ruff job" keeps
the job skeleton.

## What already exists (context)

- **Local test-runner enablement is already merged** (Task 0 of the RBAC Step 1 plan;
  see `docs/superpowers/specs/2026-07-06-pr-test-ci-design.md`):
  - `server/test-requirements.txt` → `-r requirements.txt` + `pytest==8.*`.
  - `pyproject.toml` → correct `[tool.pytest.ini_options]` with `pythonpath = ["."]`
    and `testpaths = ["server", "orm"]`.
  - The suite uses an **in-memory SQLite** fixture (`orm/eyened_orm/utils/sqlite_testdb.py`)
    with dummy DB creds set by `server/tests/conftest.py::pytest_configure` — **no live
    MySQL, no services, no secrets** in CI.
- **`client-ci.yml`** (frontend gate) is merged and is the current house style: one
  workflow per area, `actions/checkout@v7`, path-filtered, PR-only trigger.

### Dependency note (investigated, not a blocker)

`server/requirements.txt` pins `httpxyz>=0.31.2`, imported in `server/config.py` and
`server/routes/auth.py` (OIDC). `httpxyz` is a legitimate, **available** "friendly
fork" of `httpx` on PyPI (latest 0.31.2, requires Python ≥3.9); it resolves fine on
CI's Python 3.12. **Not a CI blocker, out of scope here.** Neutral observation only: the
repo depends on a third-party httpx *fork* in its auth path — a team question, not this
branch's.

## Approach (inherited, approved)

**Approach A — native runner**: check out, `pip install` deps + pytest, run `pytest`
directly on `ubuntu-latest`. Chosen over a Docker-based stage for local/CI symmetry; the
suite is pure in-memory SQLite so there is no prod-parity benefit to Docker today.

## Design principle: CI is read-only

No CI job may mutate committed source, and the workflow never pushes to the repo.
`pytest` does not modify source. `pip install -e ./orm` writes an ephemeral `*.egg-info/`
build artifact into the runner checkout; it is never committed or pushed and does not
alter source. (When the deferred ruff job lands, it must likewise be read-only: `ruff
check` without `--fix`, `ruff format --check`.)

## Design

### 1. New workflow: `.github/workflows/server-ci.yml`

One job — `test`.

```yaml
name: Server CI
on:
  push:
    branches: [development, main]
    paths:
      - 'server/**'
      - 'orm/**'
      - 'pyproject.toml'
      - '.github/workflows/server-ci.yml'
  pull_request:
    branches: [development, main]
    paths:
      - 'server/**'
      - 'orm/**'
      - 'pyproject.toml'
      - '.github/workflows/server-ci.yml'

concurrency:
  group: server-ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip
      - run: |
          python -m pip install --upgrade pip
          pip install -e ./orm
          pip install -r server/test-requirements.txt
      - run: pytest
```

**Rationale for key choices:**

- **`push` + `pull_request`, both scoped to `[development, main]`.** PR runs test the
  synthetic merge preview; the `push` runs test the *real* post-merge HEAD of the
  integration branches. Because `development` is an active multi-PR integration branch,
  the `push` run catches **merge-skew breakage** that PR-only cannot see. Scoping `push`
  to the base branches means feature-branch pushes do **not** double-run (only their PR
  run fires) — no duplicate-run waste.
- **`concurrency: cancel-in-progress`.** Cancels a still-running run when a newer commit
  supersedes it on the same ref. Never crosses refs/PRs.
- **Path filter** mirrors `client-ci.yml`, so backend CI skips on frontend-only PRs.
  *Caveat:* if `server-ci` is later made a **required** status check, a path-skipped run
  reports as skipped and branch protection can treat a required-but-skipped check as
  unsatisfied. Handle at that point (e.g. a required aggregating gate job) — not now.
- **`python-version: "3.12"`** matches `dev/Dockerfile.server` (`python:3.12-slim`). No
  matrix (YAGNI).
- **`actions/checkout@v7` + `actions/setup-python@v6`** — current latest majors.
- **`pip install -e ./orm`** (editable) mirrors how the suite resolves the ORM locally;
  it is the only source of SQLAlchemy et al. and must be importable at collection time.

### 2. Modify `.github/workflows/client-ci.yml`

Bring it in line with the agreed trigger/concurrency policy — **steps unchanged**:

- Change trigger from `pull_request` only → **`push` + `pull_request`**, both scoped to
  `[development, main]` with the existing `client/**` + workflow-file path filter.
- Add:
  ```yaml
  concurrency:
    group: client-ci-${{ github.ref }}
    cancel-in-progress: true
  ```

### Deferred: ruff job (follow-up, not in #118)

A `lint-python` (ruff) job was planned but descoped after a first run measured a large
baseline (125 `ruff check` errors, 121 files needing `ruff format`). Bundling that
cleanup here would bury the CI change and collide with in-flight branches. Tracked in
`docs/backlog/2026-07-16-backend-ruff-lint-followup.md`. Job skeleton for when it lands:

```yaml
  lint-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/ruff-action@v3
        with: { version: "0.14.x", args: check server orm }   # no --fix (read-only)
      - uses: astral-sh/ruff-action@v3
        with: { version: "0.14.x", args: format --check server orm }
```

## Prerequisite / risk

**The existing suite must be green in a clean Python-3.12 install before the gate is
trusted.** Nobody has run it in a from-scratch CI-like environment (the shared
`dev/.venv` is pre-populated; a cross-worktree run hit an import-path artifact, not a
real result). Implementation MUST first reproduce the CI recipe in a throwaway 3.12 venv
(`pip install -e ./orm` + `pip install -r server/test-requirements.txt` + `pytest`) and
confirm green. If anything is red, surface and decide **before** enabling a gate that
would block every PR.

## Testing

- Validate `server-ci.yml` and the `client-ci.yml` edit with `actionlint` locally
  before pushing.
- Prove the gate end-to-end by opening the #118 PR into `development` and confirming the
  `test` job runs and passes on the real runner.

## Out of scope

- Ruff / Python lint gate — deferred to `docs/backlog/2026-07-16-backend-ruff-lint-followup.md`.
- Docker-based test stage (Approach B) — revisit if tests ever exercise real MySQL.
- Cloud CD / deployment changes; migrating dependency management to `pyproject`.
- The `httpxyz` → upstream-`httpx` question (team decision; see note above).
