# Backend CI (tests) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Actions gate that runs the backend pytest suite on push/PR into `development`/`main`, and align `client-ci.yml` to the same trigger + concurrency policy.

**Architecture:** Native runner (Approach A) — `actions/setup-python` → `pip install -e ./orm` + `pip install -r server/test-requirements.txt` → `pytest`. No services/secrets (suite is in-memory SQLite). Two workflow files touched: a new `server-ci.yml` and an edit to the existing `client-ci.yml`.

**Tech Stack:** GitHub Actions, Python 3.12, pytest 8.x, `actions/checkout@v7`, `actions/setup-python@v6`, `actionlint` (local validation).

## Global Constraints

- **Base branch:** `development`. Open the eventual PR into `development`.
- **Python:** `3.12` (matches `dev/Dockerfile.server`). No matrix.
- **Actions (current latest majors):** `actions/checkout@v7`, `actions/setup-python@v6`.
- **Triggers:** `push` **and** `pull_request`, both scoped to `branches: [development, main]`, both path-filtered.
- **Concurrency:** every workflow gets `concurrency: { group: <name>-${{ github.ref }}, cancel-in-progress: true }`.
- **CI is read-only:** no job mutates committed source; the workflow never pushes back.
- **Ruff/linting is OUT OF SCOPE** — tracked in `docs/backlog/2026-07-16-backend-ruff-lint-followup.md`.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: Confirm a green test baseline in a clean Python 3.12 env

Load-bearing prerequisite: the suite has never been proven green in a from-scratch, CI-like install. Do this **before** writing any workflow — if it is red, stop and surface it; a gate on a red suite would block every PR.

**Files:**
- Touches no repo files (throwaway venv only).

- [ ] **Step 1: Create a fresh 3.12 venv (mirrors the runner)**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/118-run-backend-tests-in-github-actions
VENV=/tmp/claude-1011/-home-kdatta-workspace-eyened-platform/162d8da9-c212-4d6d-8907-8a8d47848481/scratchpad/ci-venv312
rm -rf "$VENV"
/usr/bin/python3.12 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
```

Expected: pip upgrades cleanly; `"$VENV/bin/python" --version` → `Python 3.12.x`.

- [ ] **Step 2: Install exactly what CI installs**

```bash
"$VENV/bin/pip" install -e ./orm
"$VENV/bin/pip" install -r server/test-requirements.txt
```

Expected: both succeed. `httpxyz>=0.31.2` and `numpy==2.0.0` resolve on 3.12 (they failed earlier only under Python 3.8).

- [ ] **Step 3: Run the full suite**

```bash
"$VENV/bin/pytest" -q
```

Expected: **all tests pass, 0 failures / 0 errors** (a clean fresh install avoids the cross-worktree `ImportPathMismatchError` seen with the shared `dev/.venv`). Record the passing test count.

- [ ] **Step 4: Decision gate (no commit — verification only)**

- **All green** → proceed to Task 2.
- **Any red** → STOP. Report the failures; do not add a CI gate on a red suite. Decide whether to fix tests first (new scope) or quarantine.

---

### Task 2: Add `.github/workflows/server-ci.yml` (test gate)

**Files:**
- Create: `.github/workflows/server-ci.yml`

- [ ] **Step 1: Write the workflow file**

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

- [ ] **Step 2: Install actionlint (workflow validator)**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/118-run-backend-tests-in-github-actions
BIN=/tmp/claude-1011/-home-kdatta-workspace-eyened-platform/162d8da9-c212-4d6d-8907-8a8d47848481/scratchpad/bin
mkdir -p "$BIN"
bash <(curl -fsSL https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash) latest "$BIN" 2>/dev/null && echo "actionlint at $BIN/actionlint"
```

If the download is blocked, fallback structural check:
```bash
/usr/bin/python3.12 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/server-ci.yml')); print('yaml OK')"
```
(If PyYAML is absent in the system 3.12, use the Task 1 venv's python.)

- [ ] **Step 3: Validate the workflow**

```bash
"$BIN/actionlint" .github/workflows/server-ci.yml
```
Expected: **no output, exit 0** (actionlint prints nothing when clean). Fix any reported issue (unknown action version, YAML error, shell quoting) and re-run.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/server-ci.yml
git commit -m "ci(server): run backend pytest suite on push/PR into development,main

New Server CI workflow: setup-python 3.12, pip install -e ./orm +
test-requirements, pytest. push+pull_request scoped to base branches,
path-filtered, cancel-in-progress. No services/secrets (in-memory SQLite).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Align `client-ci.yml` (add push trigger + concurrency)

**Files:**
- Modify: `.github/workflows/client-ci.yml`

**Interfaces:**
- Consumes: the existing `client-ci.yml` (currently `pull_request`-only, path-filtered, no concurrency). Steps must stay byte-for-byte unchanged.

- [ ] **Step 1: Read the current file to anchor the edit**

```bash
cat .github/workflows/client-ci.yml
```
Confirm it currently begins with `on:` → `pull_request:` → `branches: [main, development]` + `paths: ['client/**', '.github/workflows/client-ci.yml']`, and has `defaults:` / `jobs:` below.

- [ ] **Step 2: Add a `push` trigger mirroring the existing `pull_request` block**

Replace the `on:` block so it reads (keep the exact `paths` list already present):

```yaml
on:
  push:
    branches: [main, development]
    paths:
      - 'client/**'
      - '.github/workflows/client-ci.yml'
  pull_request:
    branches: [main, development]
    paths:
      - 'client/**'
      - '.github/workflows/client-ci.yml'
```

- [ ] **Step 3: Add a concurrency block immediately after the `on:` block**

```yaml
concurrency:
  group: client-ci-${{ github.ref }}
  cancel-in-progress: true
```

Leave `defaults:`, `jobs:`, and all steps unchanged.

- [ ] **Step 4: Validate**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/118-run-backend-tests-in-github-actions
BIN=/tmp/claude-1011/-home-kdatta-workspace-eyened-platform/162d8da9-c212-4d6d-8907-8a8d47848481/scratchpad/bin
"$BIN/actionlint" .github/workflows/client-ci.yml
git diff .github/workflows/client-ci.yml
```
Expected: actionlint exit 0; the diff shows **only** the added `push:` trigger and `concurrency:` block — no step changes. (Shell env vars do not persist across steps/tasks, so `BIN` is re-set here.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/client-ci.yml
git commit -m "ci(client): also run on push to development,main + cancel-in-progress

Aligns client CI with the new server CI trigger/concurrency policy so the
integration branches get a post-merge run. Steps unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Prove the gate end-to-end on GitHub

A workflow file is only truly validated by a real run. This task pushes the branch and opens the PR into `development`.

**Files:**
- No repo file changes.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin 118-run-backend-tests-in-github-actions
```
(The remote branch exists at the old fork point; since this branch was rebased onto `development` and never shared, a `--force-with-lease` is acceptable if the push is rejected as non-fast-forward: `git push --force-with-lease -u origin 118-run-backend-tests-in-github-actions`.)

- [ ] **Step 2: Open a PR into `development`**

Use the GitHub UI (no `gh` CLI on this host), base `development`, head `118-run-backend-tests-in-github-actions`. Title: `ci: run backend tests in GitHub Actions (#118)`. Body: link the design spec and note ruff is deferred to the backlog.

- [ ] **Step 3: Confirm the live run**

On the PR's Checks tab, confirm **Server CI / test** runs and **passes**, and that **Client CI** does *not* run for this PR (it only touches `.github/**`, `server/**`, `docs/**` — no `client/**`), demonstrating the path filter works.

- [ ] **Step 4: Decision gate**

- **Green** → done; request review.
- **Red on the runner but green locally** → investigate the environment delta (Python patch, network install, cache) before merging; do not disable the check to force it green.

---

## Notes for the executor

- Do **not** add `--fix`, `ruff`, formatting, or any source-mutating step — read-only CI is a hard constraint.
- Do **not** add MySQL/Redis services or secrets — the suite is self-contained SQLite.
- If Task 1 is red, the plan stops there; fixing the suite is a separate scope decision for the user.
