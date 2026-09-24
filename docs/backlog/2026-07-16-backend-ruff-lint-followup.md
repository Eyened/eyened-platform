# Follow-up: backend Python lint gate (ruff)

- **Source:** Descoped from issue #118 (backend test CI) during design/planning,
  2026-07-16. See [design spec](../superpowers/specs/2026-07-16-backend-ci-design.md).
- **Related prior art:** PR #49 "WIP: Code linting checks" — a ruff draft that is
  now **closed unmerged**, so there is no branch waiting to be picked up;
  the frontend prettier sweep in `client-ci.yml` (its own dedicated effort, which
  surfaced real bugs).

#118 ships the **pytest** gate only. A ruff job was planned (Scope B) but a first run
showed the cleanup is a sizeable, risky initiative that deserves its own focused PR
rather than being bundled into the CI-wiring change.

---

## 1. Backend ruff lint + format gate

**Status:** open

**What:** Add a `lint-python` job to `.github/workflows/server-ci.yml` running
`ruff check server orm` and `ruff format --check server orm` (read-only: no `--fix`),
ruff version pinned, plus `[tool.ruff]` config in `pyproject.toml`. Bring the tree to
a green baseline first, ratcheting rules up per-code.

**Why:** Automated lint/format catches regressions and keeps the backend consistent,
matching the frontend gate. Deferred because the baseline is large and mixing a
mechanical sweep into #118 would bury the CI change and collide with in-flight
branches (RBAC, search-refactor).

**Measured baseline** (ruff 0.14.14, scope `server orm`, default E/F rules,
on `development` @ 4a70c44):

- `ruff check`: **125 errors** — 67 F401 unused-import, 17 F403 star-import,
  11 F821 undefined-name, 10 F541 f-string, plus E711/E402/F841/E722/F811/E712/E721.
  60 auto-fixable (`--fix`), 10 more with `--unsafe-fixes`.
- `ruff format --check`: **121 files would be reformatted** (103 already clean).

**Those figures are a 2026-07-16 snapshot and must be re-measured before the work
is scoped.** `4a70c44` is the merge of #145; six substantial branches have landed
on `development` since — #165, #171, #195, #208, #212, #216 — none of them under a
lint gate.

**How to approach (do NOT bulk `--fix`):**
1. **Formatting PR (isolated, mechanical):** run `ruff format server orm` as one
   commit once in-flight backend branches have merged; then add `ruff format --check`
   to the job.
2. **Lint PR(s), ratcheted:** start `[tool.ruff.lint] select` from the safe subset
   (F541; F401 only after reviewing for intended re-exports), expanding `select`
   per-code as each reaches zero.
3. **Investigate, don't silence:** F403 star-imports and the 11 F821 undefined-names
   may be **real latent bugs** — review individually.

Job skeleton is captured in the design spec (§"Deferred: ruff job").
