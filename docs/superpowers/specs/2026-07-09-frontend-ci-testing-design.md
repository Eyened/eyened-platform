# Frontend CI + Testing — Design

**Date:** 2026-07-09 (revised 2026-07-13 — phased delivery + node 24, after a read-only dry run)
**Status:** Approved design; **phased delivery** — each phase ships as its own green PR.
**Scope:** Frontend = `client/` (SvelteKit 5 runes, Vite 6, TypeScript, Tailwind 4).

**Goal:** Add a frontend CI gate that runs on every PR into `main`/`development`,
mirroring the parallel backend PR-test-CI design
(`docs/superpowers/specs/2026-07-06-pr-test-ci-design.md`). Two things ship together
(now spread across phases):

1. **Make the quality gate real** — add the missing `lint`/`format` npm scripts and
   replace the broken eslint config so `lint` actually runs.
2. **Introduce a test framework** — Vitest + `@testing-library/svelte` + jsdom, with a
   small green baseline (a few pure-util unit tests + one non-canvas component render).

Delivered as a **phased rollout** (see *Phased delivery* below) so each area lands as an
independently green PR and the CI gate is **never red** — each phase adds only gate steps
that already pass.

---

## Dry-run findings (2026-07-13)

A read-only dry run on worktree HEAD `ac277bd` (`npm ci`, then `check`/`build`, plus a
throwaway flat-config `eslint .` + `prettier --check`, node 22) measured the real baseline
— **this reshaped delivery into phases**:

| Gate step | Result | Detail |
|---|---|---|
| `npm run check` (svelte-check) | ❌ **RED** | **158 errors + 103 warnings** in 129 files |
| `npm run build` (vite build) | ✓ green | 28s (vite strips types, so type errors don't fail it) |
| `eslint .` (spec flat config) | ❌ **483 errors** | 144 files; only **7 auto-fixable** |
| `prettier --check .` | ❌ **157 files** | fully auto-fixable via `prettier --write` |

**eslint 483 breakdown:** `283` `@typescript-eslint/no-explicit-any` · `61` `no-unused-vars`
· `51` `svelte/require-each-key` · `17` `svelte/no-unused-svelte-ignore` · `10`
`no-useless-assignment` · smaller tails. **20 "parse errors"** on `*.svelte.ts` files were
a *throwaway-config artifact* (the TS parser wasn't wired for the `.svelte.ts` extension) —
not real defects, but they flag a real config task (Phase 3 must wire the parser for
`.svelte.ts`).

**Correction to prior analysis:** the earlier note that *"type check works ✅"* is **false**
on this HEAD — `check` is red. The 158 svelte-check errors are TypeScript-compiler driven
(the `typescript` package), **not** node-runtime dependent, so node 20/22/24 all report them.
The samples smell like **generated-type drift** rather than 158 independent bugs — e.g.
`instanceIDs: string[]` vs `number[]` and *"Two different types with this name exist, but
they are unrelated"* point at stale `src/types/openapi.ts` / `.svelte-kit` types. Phase 4
root-causes this before committing to a fix size.

---

## Current-setup analysis

- **Frontend:** SvelteKit 5 (runes), Vite 6, TypeScript, Tailwind 4. ~310 `.svelte`
  + ~144 `.ts` files. npm lockfile (`client/package-lock.json`) present.
- **Type check is currently RED:** `npm run check` (`svelte-check`) → 158 errors (see
  *Dry-run findings*). ❌ (Phase 4.)
- **Lint/format configured but never run:** `.eslintrc.cjs` (eslint 8) and `.prettierrc`
  (prettier 3, tabWidth 4) exist, but there is **no `lint`/`format` npm script**, and
  `.eslintrc.cjs` extends **`@sveltejs/eslint-config-svelte`, which is not declared and
  is absent from the lockfile** — so lint has genuinely never executed here.
- **Installed lint toolchain:** `eslint@8.57.1`, `eslint-plugin-svelte@2.46.1` (v2
  supports legacy `.eslintrc`; v3+ would force flat config), `svelte-eslint-parser@0.43.0`,
  `@typescript-eslint/parser@6.21.0` — all present (some transitive).
- **Existing custom scripts:** `verify:runes` (rg guard against `export let`),
  `check:unused` (unimported).
- **No test framework at all** — no vitest/playwright, zero test files. Biggest gap.
- **Existing CI:** only `.github/workflows/deploy.yml` (Astro docs → GitHub Pages on
  push to `main`). **No PR checks run today.** The docs deploy defaults to node 20 — this
  design moves the frontend gate to **node 24** (see decision below); aligning `deploy.yml`
  is optional and out of scope.

---

## Decisions

### Testing scope — gate + Vitest unit/component (no E2E)

CI runs the quality gate **and** a small Vitest suite. E2E (Playwright) is out of
scope: it would need the backend + DB stood up in CI (the app uses `openapi-fetch`,
DICOM, WebGL), a meaningfully bigger and flakier lift. Revisit later.

### Component-test setup — jsdom + Testing Library (not browser mode)

`vitest` + `@testing-library/svelte` + `@testing-library/jest-dom` + `jsdom`.

Chosen over Vitest **browser mode** (`vitest-browser-svelte` + Playwright chromium)
because tests run in **GitHub Actions**: jsdom is pure Node — nothing to install
beyond `npm ci`, runs in seconds, deterministic, no browser binary to download/cache
and no extra flake surface. Browser mode ages better for this WebGL/canvas/DICOM-heavy
app, but that value only appears once we test canvas components; for a first pass of
pure-util units + one simple component render, jsdom is the lower-friction choice. A
browser-based Vitest *project* can be added later, incrementally, when we start testing
components that need a real canvas.

This matches the official Svelte 5 testing guidance
(<https://svelte.dev/docs/svelte/testing>), which recommends **Vitest**, the **jsdom**
environment, and calls out **`@testing-library/svelte`** as a helpful abstraction.

### Node baseline — node 24 (LTS)

The frontend gate runs on **node 24** (current LTS "Krypton", since Oct 2025) — a clean
upgrade from the node 20 the docs-deploy defaults to (node 20 nears end of active support).
Our toolchain (Vite 6, Vitest 4, eslint 10, svelte-check, prettier) all support node 24.

- **CI** pins node via `actions/setup-node` reading **`client/.nvmrc`** (single source of
  truth: `24`), so the workflow and local dev can't drift.
- **`client/.nvmrc`** (`24`) lets local devs `nvm use` to match CI. `package.json`
  `"engines": { "node": ">=24" }` is added as a soft guard.
- **Verification (Phase 1):** the dry-run baseline was measured on node 22; Phase 1 must
  confirm `test`/`build` are green under node 24. Type-check (Phase 4) is node-independent.
- Aligning the docs `deploy.yml` (node 20) to 24 is **out of scope** but noted for later
  consistency.

### ESLint — modern flat config (eslint 10) + TS linting

The existing `.eslintrc.cjs` is already broken (extends the never-installed
`@sveltejs/eslint-config-svelte`) and eslint 8 is **end-of-life** — so rather than
resurrect a dead-major legacy config, we replace it with a **flat config**
(`eslint.config.js`) on the current toolchain. eslint 10 removes eslintrc support
entirely, so flat config is the only path forward anyway.

Composition (all peer-compatible with our stack — svelte 5.34, TS 5, vite 6, node 24):
- `@eslint/js` recommended — base JS rules.
- **`typescript-eslint`** recommended, **non-type-aware** (`tseslint.configs.recommended`,
  *not* `recommendedTypeChecked`) — no `parserOptions.project` wiring, no slow
  type-aware pass. This lints `.ts` for the first time in this repo.
- **`eslint-plugin-svelte@3`** flat recommended (+ `svelte-eslint-parser`), with the TS
  parser wired into `<script lang="ts">` blocks **and into the `*.svelte.ts` / `*.svelte.js`
  rune-module extensions** (the dry run's 20 parse errors came from missing this — see
  *Dry-run findings*).
- **`eslint-config-prettier`** (flat) applied last, to switch off formatting rules that
  would fight prettier.
- the custom `no-restricted-syntax` **`export let` guard**, ported into the `.svelte`
  block of the flat config.

**Lint scope widens to `.svelte` + `.js` + `.ts`.** `svelte-check`/`tsc` still own type
*correctness*; eslint now adds lint rules on `.ts` as well. **Reaching green (Phase 3):**
the dry run measured **483 errors** — `283` are `@typescript-eslint/no-explicit-any`
(dominant; disable or downgrade-to-warn as a baseline decision erases them in one stroke),
`~7` auto-fix via `eslint --fix`, and the rest (`no-unused-vars`, `require-each-key`,
`prefer-const`, `no-var`, …) are largely mechanical. Per-rule decision (fix vs
downgrade/disable) reaches a green baseline without a mass rewrite.

---

## Design

### 1. `client/` tooling changes

**New devDeps** — added via `npm install -D <pkg>@<range>`, which writes caret ranges
consistent with the existing `^x.y.z` entries in `package.json` (no bare names, no
`latest`). Latest majors verified against npm on 2026-07-09:

_Testing:_
- `vitest@^4` (4.1.10; peer `vite ^6||^7||^8` — compatible with our Vite 6)
- `@testing-library/svelte@^5` (5.4.2; supports Svelte 5)
- `@testing-library/jest-dom@^6` (6.9.1)
- `jsdom@^29` (29.1.1)

_Lint (flat config):_
- `eslint@^10` (10.6.0) — **bump from the current `^8`**
- `@eslint/js@^10` (10.0.1)
- `typescript-eslint@^8` (8.63.0; TS peer `>=4.8.4 <6.1.0`, our TS 5 fits)
- `eslint-plugin-svelte@^3` (3.20.0; peer eslint `^8.57||^9||^10`)
  \+ `svelte-eslint-parser@^1` (1.8.0)
- `eslint-config-prettier@^10` (10.1.8, flat-compatible) — **bump from the current `^8`**
- `globals@^17` (17.7.0)

**Config change:** **delete `.eslintrc.cjs`**, add **`eslint.config.js`** (flat)
composing the pieces from the ESLint decision above and porting the `export let` guard.
(eslint 10 no longer reads `.eslintrc.*`.)

**New npm scripts** (`client/package.json`):

```json
{
  "lint": "eslint . && prettier --check .",
  "format": "prettier --write .",
  "test": "vitest run",
  "test:watch": "vitest"
}
```

With flat config, `eslint .` lints every file matched by the config's `files` patterns
(`.js` / `.ts` / `.svelte`) — no `--ext` (it's removed in flat config). Ignores are
declared in `eslint.config.js` (a `{ ignores: [...] }` block) rather than a separate
`.eslintignore`. `prettier` is already configured (`.prettierrc`, tabWidth 4).
`verify:runes` already exists and stays part of the gate.

### 2. Vitest config

Fold the `test` block into **`vite.config.ts`** (using `defineConfig` from
`vitest/config`, keeping the existing plugins) so `.svelte` files compile under the
Svelte Vite plugin. A standalone `vitest.config.ts` would not apply that plugin.

Per the Svelte testing docs, set `resolve.conditions: ['browser']` **guarded by
`process.env.VITEST`** so Vitest uses the `browser` package entry points while running
in Node, without affecting the real `vite build`:

```ts
import { defineConfig } from 'vitest/config';
// ...existing plugins...

export default defineConfig({
  plugins: [/* existing */],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest-setup.ts'],
  },
  resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
});
```

`vitest-setup.ts` imports `@testing-library/jest-dom` matchers and wires
`@testing-library/svelte`'s auto-cleanup.

**Note (kept single-config on purpose):** the newest Svelte scaffolding splits Vitest
into two projects (a jsdom "client" project for component tests + a node "server"
project for pure `.ts`). We keep the single jsdom config the core doc shows — YAGNI for
a handful of tests. Add the split when the suite grows.

### 3. Test baseline

- **Unit tests** (pure logic, no DOM): `src/lib/vec2.ts`, `src/lib/matrix.ts`,
  `src/lib/utils/deferred.ts`.
- **One component test:** a simple presentational component — no canvas/WebGL, minimal
  props — rendered via `@testing-library/svelte`'s `render`, asserting on output. Exact
  component chosen during implementation.
- Goal is a **green baseline**, not coverage.

**Caveats for future component tests** (recorded for whoever writes them): call
`flushSync()` after interactions before asserting; wrap effect-dependent code in
`$effect.root`. The first component test is simple enough to avoid most of this.

### 4. CI workflow — new `.github/workflows/client-ci.yml`

Named for its broader gate role (lint + typecheck + test + build), distinct from the
backend's `tests.yml`. **Built up across phases** — each phase adds only the steps that
are green by then (see *Phased delivery*). Final shape:

```yaml
name: Client CI
on:
  pull_request:
    branches: [main, development]
    paths:
      - 'client/**'
      - '.github/workflows/client-ci.yml'

defaults:
  run:
    working-directory: client

jobs:
  client:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: client/.nvmrc   # node 24
          cache: npm
          cache-dependency-path: client/package-lock.json
      - run: npm ci
      - run: npm run verify:runes # export-let guard   (Phase 1)
      - run: npm run test         # vitest run          (Phase 1)
      - run: npm run build        # vite build          (Phase 1)
      - run: npm run format:check # prettier --check .  (Phase 2)
      - run: npm run lint         # eslint              (Phase 3)
      - run: npm run check        # svelte-check        (Phase 4)
```

- **`paths` filter:** docs/orm/server-only PRs skip the frontend gate (monorepo
  optimization).
- **node 24** via `client/.nvmrc`. **npm ci** from the committed lockfile,
  with `actions/setup-node` npm caching keyed on `client/package-lock.json`.
- **`defaults.run.working-directory: client`** runs every step in `client/`.
- One job, sequential — fast (seconds-to-a-minute), no browser binary, no services.
- **Step order = phase order**, so at every phase the whole job is green.

---

## Phased delivery

Each phase is its own PR, branched off `development`, independently green. A phase adds
its gate step **only once that step passes**, so `client-ci` is never red. Independent of
the RBAC branch (`feature/rbac-step1-service-layer`).

### Phase 1 — Test harness + minimal (green) CI  ·  node 24

- Add test devDeps (`vitest@^4`, `@testing-library/svelte@^5`, `@testing-library/jest-dom@^6`,
  `jsdom@^29`), `vite.config.ts` `test` block, `vitest-setup.ts`, `test`/`test:watch` scripts.
- Test baseline: unit tests (`vec2`/`matrix`/`utils/deferred`) + one simple component render.
- Add **`client/.nvmrc` = 24** and `engines.node >=24`.
- Introduce **`client-ci.yml`** with only the already-green steps: `verify:runes`, `test`,
  `build` — on **node 24**.
- **Exit criteria:** `client-ci` green on a PR; confirm `test`/`build` pass under node 24.
- **Risk:** low — purely additive, green by construction.

### Phase 2 — Formatting baseline (prettier)

- Add `format` (`prettier --write .`) and `format:check` (`prettier --check .`) scripts.
- Run `prettier --write .` as **one isolated mechanical commit** (~157 files) — no behavior
  change; land fast to minimize conflicts with other client work.
- Add `format:check` step to `client-ci.yml`.
- **Exit criteria:** `prettier --check .` clean; gate step green.
- **Risk:** low — 100% auto-fixable; the only cost is a large review diff.

### Phase 3 — ESLint flat config → green

- Delete `.eslintrc.cjs`; add `eslint.config.js` (flat) per the ESLint decision — **wiring
  the TS parser for `.svelte`, `.svelte.ts`, `.svelte.js`**; port the `export let` guard;
  add `lint` script; bump lint devDeps (eslint 10 + plugins).
- Reach green from the measured **483**: decide `@typescript-eslint/no-explicit-any`
  baseline (disable / warn) → −283; `eslint --fix` the auto-fixables; resolve the mechanical
  remainder per-rule (fix vs downgrade/disable in `eslint.config.js`).
- Add `lint` step to `client-ci.yml`.
- **Exit criteria:** `eslint .` clean; gate step green.
- **Risk:** medium — bounded by the rule-baseline decision + mechanical fixes.

### Phase 4 — svelte-check remediation → green

- **Root-cause the 158 first** (cheap): are they real type bugs or generated-type/stale-sync
  drift (`src/types/openapi.ts`, `.svelte-kit`)? Regenerate/align drifted types, then fix the
  genuine remainder. **Sub-phase** if the real count is large.
- Add `check` step to `client-ci.yml`.
- **Exit criteria:** `npm run check` clean; gate step green.
- **Risk:** highest / unknown until root-caused — **quarantined last** so it blocks nothing
  above.

### Enabling enforcement (manual, post-phases — repo admin)

Merging the phases makes `client-ci` **run** and report a ✓/✗ on qualifying PRs, but it
does **not** block merges on its own. To gate merges, a repo admin adds the workflow's
status check as a **required status check** in the branch-protection rules for `main`
and `development` (GitHub → Settings → Branches → the rule → "Require status checks to
pass before merging" → select `client-ci`). One-time manual step, outside the workflow
file.

**Interaction with the `paths:` filter (handle only when enforcing):** a *path-filtered*
workflow that is skipped never reports its check, so once `client-ci` is required, a PR
that doesn't touch `client/**` would be blocked forever waiting for a run that never
happens. Fix at that time by moving the change-detection off `on.paths` and into a
job-level guard (e.g. `dorny/paths-filter` / a `changed-files` step) so the check always
reports. Not needed until enforcement is turned on.

---

## Out of scope

- Playwright / E2E, and standing up backend + DB in CI.
- Vitest **browser mode** (`vitest-browser-svelte`) and testing canvas/WebGL/DICOM
  components.
- **Type-aware** typescript-eslint linting (`recommendedTypeChecked` + `parserOptions.
  project`) — we use the fast non-type-aware `recommended` only.
- Splitting Vitest into client/server projects.
- Actually **configuring** branch protection / required checks — that manual admin step
  (and its `paths`-filter interaction) is documented under *Enabling enforcement*; the
  phases only make the workflow run and report.
- Post-merge `push` triggers and cloud CD.
- Upgrading the docs `deploy.yml` to node 24 (noted for consistency, not done here).

---

## Consistency with backend CI

Keep this workflow and the backend `tests.yml` aligned: both are separate workflows on
`pull_request: branches: [main, development]`, both use native runners with dependency
caching and run the same commands a developer runs locally. See
`docs/superpowers/specs/2026-07-06-pr-test-ci-design.md` and the `pr-test-ci-setup`
memory.
