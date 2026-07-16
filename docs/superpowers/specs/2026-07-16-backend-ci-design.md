# Backend CI (tests + Python lint) — Design

**Date:** 2026-07-16
**Issue:** #118 — run backend tests in GitHub Actions
**Base branch:** `development`
**Status:** Approved design; implementation pending.

## Goal

Add a GitHub Actions gate that runs the backend **test suite** and **Python linting**
on every pull request into `development`/`main` and on every push to those branches,
using the same commands a developer runs locally. Keep the two frontend/backend gates
stylistically consistent.

## What already exists (context)

- **Local test-runner enablement is already merged to `main`** (it was Task 0 of the
  RBAC Step 1 plan; see `docs/superpowers/specs/2026-07-06-pr-test-ci-design.md`):
  - `server/test-requirements.txt` → `-r requirements.txt` + `pytest==8.*`.
  - `pyproject.toml` → correct `[tool.pytest.ini_options]` with
    `pythonpath = ["."]` and `testpaths = ["server", "orm"]`.
  - The suite uses an **in-memory SQLite** fixture (`orm/eyened_orm/utils/sqlite_testdb.py`)
    with dummy DB creds set by `server/tests/conftest.py::pytest_configure` — **no live
    MySQL, no services, no secrets** needed in CI.
- **`client-ci.yml`** (frontend gate) is already merged and is the current house style:
  one workflow per area, `actions/checkout@v7`, path-filtered.
- **PR #49 ("WIP: Code linting checks")** is an unmerged draft that added a
  `checks.yml` with a **ruff** Python-lint job and a TypeScript-lint job. Its
  TypeScript half is superseded by `client-ci.yml`; its **ruff job is the useful part
  we revive here**. It confirmed Python **3.12** and `actions/setup-python@v6`.

### Dependency note (investigated, not a blocker)

`server/requirements.txt` pins `httpxyz>=0.31.2`, imported in `server/config.py` and
`server/routes/auth.py` (OIDC flows). Investigation (2026-07-16): `httpxyz` is a
legitimate, **currently-available** "friendly fork" of `httpx` on PyPI (latest 0.31.2,
2026-05-08; requires Python ≥3.9). An earlier "removed from PyPI" reading was a
Python-3.8 install artifact and is **wrong** — it resolves fine on CI's Python 3.12.
**Not a CI blocker and out of scope here.** The only neutral observation: the repo
depends on a third-party httpx *fork* in its auth path; whether that is intentional is
a question for the team, not for this branch.

## Design principle: CI is read-only

No CI job may mutate committed source. All checks are report-only and the workflow
never pushes to the repo:

- `ruff check` runs **without `--fix`**; `ruff format` runs **with `--check`** — both
  only report and fail, never rewrite files.
- `pytest` does not modify source.
- The only mutating command, plain `ruff format server orm`, is a **one-time local
  commit** during implementation (§2) — never a workflow step.
- `pip install -e ./orm` writes an ephemeral `*.egg-info/` build artifact into the
  runner checkout; it is never committed or pushed and does not alter source.

## Approach (inherited, approved)

**Approach A — native runner**: check out, `pip install` deps + pytest, run `pytest`
directly on `ubuntu-latest`. Chosen over a Docker-based stage for local/CI symmetry;
the suite is pure in-memory SQLite so there is no prod-parity benefit to Docker today.
Linting runs via `astral-sh/ruff-action`, matching PR #49's mechanism.

## Design

### 1. New workflow: `.github/workflows/server-ci.yml`

Two jobs — `test` and `lint-python` — under a shared trigger.

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

  lint-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/ruff-action@v3
        with:
          version: "0.14.x"   # verify latest at implementation; pin for reproducibility
          args: check server orm
      - uses: astral-sh/ruff-action@v3
        with:
          version: "0.14.x"
          args: format --check server orm
```

**Rationale for key choices:**

- **`push` + `pull_request`, both scoped to `[development, main]`.** PR runs test the
  synthetic merge preview; the `push` runs test the *real* post-merge HEAD of the
  integration branches. Because `development` is an active multi-PR integration branch,
  the `push` run catches **merge-skew breakage** that PR-only cannot see (a stale PR
  merging green but breaking `development`). Scoping `push` to the base branches means
  feature-branch pushes do **not** double-run (only their PR run fires), so there is no
  duplicate-run waste.
- **`concurrency: cancel-in-progress`.** Cancels a still-running run when a newer commit
  supersedes it on the same ref, saving CI minutes. Never crosses refs/PRs.
- **Path filter** mirrors `client-ci.yml`, so backend CI skips on frontend-only PRs.
  *Caveat:* if `server-ci` is later made a **required** status check, a path-skipped run
  reports as skipped and branch protection can treat a required-but-skipped check as
  unsatisfied. Handle at that point (e.g. a required "always-green" gate job) — not now.
- **Two separate jobs** (not chained steps) so a lint failure and a test failure are
  independently visible and can run in parallel.
- **Ruff scoped to `server orm`** — excludes `dev/` scripts and `notebooks/` (Jupyter),
  matching PR #49's intent to skip notebooks.

### 2. Ruff baseline (make `lint-python` green without a giant fix-PR)

Ruff has **never** been run on the backend, so `ruff check`/`format --check` could
surface many findings. The gate must land green. Strategy:

1. **Add `[tool.ruff]` config to root `pyproject.toml`** (alongside the pytest config):

   ```toml
   [tool.ruff]
   target-version = "py312"
   # line-length defaults to 88

   [tool.ruff.lint]
   select = ["E", "F"]   # ruff defaults; conservative starting set
   ```

   This makes a local `ruff check server orm` match CI exactly.

2. **Measure first (execution step):** run `ruff format --check server orm` and
   `ruff check server orm` and count findings.
   - **Formatting:** apply `ruff format server orm` once as a single mechanical commit,
     so `format --check` is green.
   - **Lint (`check`):** if the residual finding count is small, fix them. If large,
     narrow the initial `select` (or add `extend-ignore` / `per-file-ignores`) so the
     gate is green now, and record a follow-up to ratchet rules up over time. **The
     exact starting rule set is decided from the measured count, not guessed.**

3. **Pin the ruff version** in the action (reproducible gate); verify the current latest
   at implementation rather than trusting this doc's placeholder.

### 3. Modify `.github/workflows/client-ci.yml`

Bring it in line with the agreed trigger/concurrency policy:

- Change trigger from `pull_request` only → **`push` + `pull_request`**, both scoped to
  `[development, main]` with the existing `client/**` + workflow path filter.
- Add a `concurrency: { group: client-ci-${{ github.ref }}, cancel-in-progress: true }`
  block.

No change to its steps.

## Prerequisite / risk

**The existing suite must be green in a clean Python-3.12 install before the gate is
trusted.** Nobody has run it in a from-scratch CI-like environment (the shared
`dev/.venv` is pre-populated, and a cross-worktree run hit an import-path artifact, not
a real result). Implementation MUST first reproduce the CI recipe in a throwaway 3.12
venv (`pip install -e ./orm` + `pip install -r server/test-requirements.txt` +
`pytest`) and confirm green. If anything is red, surface and decide **before** enabling
a gate that would block every PR.

## Testing

- Validate `server-ci.yml` and the `client-ci.yml` edit with a YAML/action linter
  (e.g. `actionlint`) locally before pushing.
- Prove the gate end-to-end by opening the #118 PR into `development` and confirming
  both jobs run and pass on the real runner.

## Out of scope

- Docker-based test stage (Approach B) — revisit if tests ever exercise real MySQL.
- Cloud CD / deployment changes.
- Migrating dependency management to `pyproject`.
- The `httpxyz` → upstream-`httpx` question (team decision; see note above).
- Expanding the ruff rule set beyond the agreed green baseline (fast-follow).
- Reviving PR #49's TypeScript-lint job (superseded by `client-ci.yml`).
