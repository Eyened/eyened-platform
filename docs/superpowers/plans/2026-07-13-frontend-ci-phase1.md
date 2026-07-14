# Frontend CI — Phase 1 (Test harness + minimal green CI · node 24) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a Vitest + Testing-Library test harness in `client/`, prove it green with a small baseline suite (three pure-util test files + one component render), pin the runtime to node 24, and add a `client-ci.yml` gate that runs only the already-green steps (`verify:runes`, `test`, `build`).

**Architecture:** Vitest config is folded into the existing `client/vite.config.ts` (so `.svelte` files compile under the Svelte Vite plugin) with a `jsdom` environment and a `VITEST`-guarded `resolve.conditions: ['browser']`. Tests are co-located next to source as `*.test.ts` (Vitest's default glob). The CI workflow lives at repo root (`.github/workflows/client-ci.yml`) but runs every step in `client/` via `defaults.run.working-directory`. This phase is **purely additive** — it adds no gate step that isn't already green, so `client-ci` is green by construction.

**Tech Stack:** SvelteKit 5 (runes), Vite 6, TypeScript 5, Vitest 4, `@testing-library/svelte` 5, `@testing-library/jest-dom` 6, jsdom 29, node 24.

## Global Constraints

- **Runtime:** node **24** (LTS "Krypton"). Pin via `client/.nvmrc` = `24` and `package.json` `"engines": { "node": ">=24" }`. All local verification runs under node 24.
- **Dependency ranges (caret, matching existing `^x.y.z` style — no bare names, no `latest`):** `vitest@^4`, `@testing-library/svelte@^5`, `@testing-library/jest-dom@^6`, `jsdom@^29`. Install with `npm install -D` so the caret range is written automatically.
- **Phase-1 CI gate = `verify:runes` → `test` → `build` only.** Do **not** add `lint`/`format:check`/`check` steps — those belong to Phases 2–4 and are currently red. Step order in the workflow equals phase order.
- **This phase does NOT run `eslint`, `prettier --check`, or `svelte-check`.** Test-file code style and test-file type errors are therefore not gated here; Phase 2 normalizes formatting (`prettier --write .`) and Phase 4 owns `svelte-check`. Do not touch `tsconfig.json` in this phase.
- **`vite.config.ts` must keep every existing plugin and the existing `server`/`build` blocks** — the only edits are switching the `defineConfig` import to `vitest/config` and adding the `test` + `resolve` keys.
- **Tests are baseline/characterization tests over existing, working code.** Unlike normal TDD, the util/component tests are expected to **PASS on first run** — a red result is a real finding to investigate, not the expected state. The only genuine red→green cycle is the harness itself in Task 1 (Vitest absent → present).
- **Work happens on branch `feature/frontend-ci-testing`** in the worktree `/home/kdatta/workspace/eyened-platform-worktrees/frontend-ci-testing` (upstream unset; do not push). Commit per task.

---

## File Structure

**Create:**
- `client/.nvmrc` — single-source node version (`24`); read by CI and `nvm use`.
- `client/vitest-setup.ts` — registers jest-dom matchers + Testing-Library auto-cleanup.
- `client/src/lib/vec2.test.ts` — unit tests for `Vec2` / `vec2`.
- `client/src/lib/matrix.test.ts` — unit tests for `Matrix` / `getMatrixFromPointSets`.
- `client/src/lib/utils/deferred.test.ts` — unit tests for `DeferredMap`.
- `client/src/lib/components/SortHeader.test.ts` — one component render + interaction test.
- `.github/workflows/client-ci.yml` — the CI gate (repo root, runs in `client/`).

**Modify:**
- `client/package.json` — add test devDeps, `test`/`test:watch` scripts, `engines.node`.
- `client/vite.config.ts` — switch `defineConfig` import to `vitest/config`; add `test` block + `VITEST`-guarded `resolve.conditions`.

**Note on docs:** the design spec (`docs/superpowers/specs/2026-07-09-frontend-ci-testing-design.md`) and this plan are currently untracked. Committing them alongside Task 1 makes the PR self-documenting; keeping them local is also fine (prior preference was "keep local"). Default: commit both docs in Task 1's commit.

---

### Task 1: Test harness + node 24 baseline, proven by `vec2` unit tests

Stands up the whole test pipeline and validates it with the first real test file (`vec2`), so there is no throwaway smoke test. Ends with `npm run test` and `npm run build` green under node 24.

**Files:**
- Create: `client/.nvmrc`
- Create: `client/vitest-setup.ts`
- Create: `client/src/lib/vec2.test.ts`
- Modify: `client/package.json` (devDeps, scripts, engines)
- Modify: `client/vite.config.ts`
- Consumes (existing production code, do not modify): `client/src/lib/vec2.ts` — `class Vec2 { constructor(readonly x:number, readonly y:number); length():number; dot(o):number; sub(o):Vec2; add(o):Vec2; mul(s:number):Vec2; cross(o):number; angle():number }` and `vec2(p:{x,y}):Vec2`.

**Interfaces:**
- Produces (consumed by Tasks 2–4): the Vitest harness — `test`/`test:watch` npm scripts, `vite.config.ts` `test` block (`environment:'jsdom'`, `globals:true`, `setupFiles:['./vitest-setup.ts']`), and the `*.test.ts` co-location convention. Later tasks just add `*.test.ts` files; no further config needed.

- [ ] **Step 1: Switch to node 24**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/frontend-ci-testing/client
# nvm is at ~/.nvm but not a shell function in non-login shells; source it first:
. "$HOME/.nvm/nvm.sh"
nvm install 24 && nvm use 24
node --version   # expect v24.x
```

Expected: `v24.x.y` printed. (Local default was v22; node 24 must be active for the rest of this task.)

- [ ] **Step 2: Add the node pin**

Create `client/.nvmrc`:

```
24
```

- [ ] **Step 3: Install the test devDeps**

```bash
npm install -D vitest@^4 @testing-library/svelte@^5 @testing-library/jest-dom@^6 jsdom@^29
```

Expected: `package.json` gains the four caret-ranged devDeps and `package-lock.json` updates. (`npm` may print an `EBADENGINE`-style note only if run under node <24 — you're on 24, so none expected.)

- [ ] **Step 4: Add scripts + engines to `client/package.json`**

Add to the `"scripts"` block (after `check:unused`):

```json
    "test": "vitest run",
    "test:watch": "vitest"
```

Add a top-level `"engines"` key (e.g. after `"type": "module"`):

```json
  "engines": {
    "node": ">=24"
  },
```

- [ ] **Step 5: Create `client/vitest-setup.ts`**

```ts
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/svelte';

// Unmount any component rendered by a test so DOM state never leaks between tests.
afterEach(() => {
    cleanup();
});
```

- [ ] **Step 6: Wire the `test` block into `client/vite.config.ts`**

Replace the file's contents with (only the `defineConfig` import source changes, plus the new `test` + `resolve` keys — every existing plugin and the `server`/`build` blocks are preserved verbatim):

```ts
import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import Icons from "unplugin-icons/vite";
import { defineConfig } from "vitest/config";
import glsl from "vite-plugin-glsl";


export default defineConfig({
  plugins: [tailwindcss(), sveltekit(), glsl(), Icons({ compiler: "svelte" })],
  server: { allowedHosts: true },
  build: {
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // Remove console.logs in production
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest-setup.ts'],
  },
  // Per svelte.dev/docs/svelte/testing: use the package "browser" entry points
  // while Vitest runs in Node, without affecting the real `vite build`.
  resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
});
```

- [ ] **Step 7: Confirm the harness is red before the first test exists**

```bash
npm run test
```

Expected: Vitest runs but reports **"No test files found"** (or exits non-zero) — proves the harness is installed but has nothing to run yet.

- [ ] **Step 8: Write the first unit test — `client/src/lib/vec2.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { Vec2, vec2 } from './vec2';

describe('Vec2', () => {
    it('computes length for a 3-4-5 triangle', () => {
        expect(new Vec2(3, 4).length()).toBe(5);
    });

    it('adds and subtracts componentwise', () => {
        const a = new Vec2(1, 2);
        const b = new Vec2(3, 5);
        expect(a.add(b)).toEqual(new Vec2(4, 7));
        expect(b.sub(a)).toEqual(new Vec2(2, 3));
    });

    it('scales with mul', () => {
        expect(new Vec2(2, -3).mul(2)).toEqual(new Vec2(4, -6));
    });

    it('computes dot and cross products', () => {
        const a = new Vec2(1, 2);
        const b = new Vec2(3, 4);
        expect(a.dot(b)).toBe(11); // 1*3 + 2*4
        expect(a.cross(b)).toBe(-2); // 1*4 - 2*3
    });

    it('returns the angle via atan2', () => {
        expect(new Vec2(0, 1).angle()).toBeCloseTo(Math.PI / 2);
        expect(new Vec2(1, 0).angle()).toBe(0);
    });
});

describe('vec2 factory', () => {
    it('wraps a point into a Vec2', () => {
        const v = vec2({ x: 7, y: 8 });
        expect(v).toBeInstanceOf(Vec2);
        expect([v.x, v.y]).toEqual([7, 8]);
    });
});
```

- [ ] **Step 9: Run the suite — expect GREEN**

```bash
npm run test
```

Expected: **1 file, 6 tests, all pass.** (These characterize existing, working code — a failure means either the test or the code is wrong; investigate before proceeding.)

- [ ] **Step 10: Confirm `build` still green under node 24**

```bash
npm run build
```

Expected: vite build completes successfully (the `test`/`resolve` config keys do not affect the production build; `resolve` is `undefined` when `VITEST` is unset).

- [ ] **Step 11: Commit**

```bash
git add client/.nvmrc client/vitest-setup.ts client/vite.config.ts \
        client/package.json client/package-lock.json client/src/lib/vec2.test.ts \
        docs/superpowers/specs/2026-07-09-frontend-ci-testing-design.md \
        docs/superpowers/plans/2026-07-13-frontend-ci-phase1.md
git commit -m "test(client): add Vitest harness + node 24 baseline, prove with vec2 tests"
```

---

### Task 2: `matrix` unit tests

**Files:**
- Create: `client/src/lib/matrix.test.ts`
- Consumes (existing, do not modify): `client/src/lib/matrix.ts` — `class Matrix` with `static identity`, `static from_translate_scale(tx,ty,sx,sy)`, `static fromRows(rows:number[][])`, `apply(p)`, `applyInverse(p)`, `multiply(m)`, `get inverse` (throws `"Matrix is not invertible"`), `fromRows` throws `"Expected 3x3 matrix"`; and `getMatrixFromPointSets(src, dst): Matrix | undefined`.

**Interfaces:**
- Consumes the harness from Task 1 (no config changes). Adds one `*.test.ts` file.

- [ ] **Step 1: Write `client/src/lib/matrix.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { Matrix, getMatrixFromPointSets } from './matrix';

describe('Matrix', () => {
    it('identity maps a point to itself', () => {
        const p = Matrix.identity.apply({ x: 3, y: 5 });
        expect(p.x).toBeCloseTo(3);
        expect(p.y).toBeCloseTo(5);
    });

    it('from_translate_scale scales then translates', () => {
        const m = Matrix.from_translate_scale(10, 20, 2, 3);
        const p = m.apply({ x: 1, y: 1 });
        expect(p.x).toBeCloseTo(12); // 2*1 + 10
        expect(p.y).toBeCloseTo(23); // 3*1 + 20
    });

    it('inverse composed with the matrix yields the original point', () => {
        const m = Matrix.from_translate_scale(10, 20, 2, 3);
        const back = m.applyInverse({ x: 12, y: 23 });
        expect(back.x).toBeCloseTo(1);
        expect(back.y).toBeCloseTo(1);
    });

    it('throws when inverting a singular matrix', () => {
        const singular = new Matrix(0, 0, 0, 0, 0, 0, 0, 0, 0);
        expect(() => singular.inverse).toThrow('not invertible');
    });

    it('fromRows rejects a non-3x3 input', () => {
        expect(() => Matrix.fromRows([[1, 2], [3, 4]])).toThrow('3x3');
    });
});

describe('getMatrixFromPointSets', () => {
    it('recovers a known affine transform from point correspondences', () => {
        const src = [
            { x: 0, y: 0 },
            { x: 1, y: 0 },
            { x: 0, y: 1 }
        ];
        const truth = Matrix.from_translate_scale(5, 7, 2, 2); // scale 2 + translate (5,7)
        const dst = src.map((p) => truth.apply(p));

        const m = getMatrixFromPointSets(src, dst);
        expect(m).toBeDefined();

        const got = m!.apply({ x: 2, y: 3 });
        const expected = truth.apply({ x: 2, y: 3 });
        expect(got.x).toBeCloseTo(expected.x);
        expect(got.y).toBeCloseTo(expected.y);
    });
});
```

- [ ] **Step 2: Run — expect GREEN**

```bash
npm run test -- matrix
```

Expected: `matrix.test.ts` — 6 tests pass. (`getMatrixFromPointSets` exercises `mathjs`; runs fine in jsdom/node.)

- [ ] **Step 3: Commit**

```bash
git add client/src/lib/matrix.test.ts
git commit -m "test(client): add Matrix + getMatrixFromPointSets unit tests"
```

---

### Task 3: `DeferredMap` unit tests

**Files:**
- Create: `client/src/lib/utils/deferred.test.ts`
- Consumes (existing, do not modify): `client/src/lib/utils/deferred.ts` — `class DeferredMap<K,V>` with `get(k):Promise<V>` (resolves immediately if set, otherwise on later `set`), `getSync(k):V|undefined`, `set(k,v):void` (ignores duplicate key and `console.warn`s), `has(k):boolean`, `clear():void`.

**Interfaces:**
- Consumes the harness from Task 1. Adds one `*.test.ts` file.

- [ ] **Step 1: Write `client/src/lib/utils/deferred.test.ts`**

```ts
import { describe, it, expect, vi } from 'vitest';
import { DeferredMap } from './deferred';

describe('DeferredMap', () => {
    it('resolves get() immediately when the value is already set', async () => {
        const m = new DeferredMap<string, number>();
        m.set('a', 1);
        await expect(m.get('a')).resolves.toBe(1);
    });

    it('resolves a pending get() once the value arrives later', async () => {
        const m = new DeferredMap<string, number>();
        const pending = m.get('b');
        m.set('b', 42);
        await expect(pending).resolves.toBe(42);
    });

    it('resolves all waiters registered for the same key', async () => {
        const m = new DeferredMap<string, number>();
        const w1 = m.get('c');
        const w2 = m.get('c');
        m.set('c', 7);
        await expect(Promise.all([w1, w2])).resolves.toEqual([7, 7]);
    });

    it('getSync returns the value or undefined, and has() tracks membership', () => {
        const m = new DeferredMap<string, number>();
        expect(m.getSync('x')).toBeUndefined();
        expect(m.has('x')).toBe(false);
        m.set('x', 5);
        expect(m.getSync('x')).toBe(5);
        expect(m.has('x')).toBe(true);
    });

    it('ignores a duplicate set and warns', () => {
        const m = new DeferredMap<string, number>();
        const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
        m.set('d', 1);
        m.set('d', 2);
        expect(m.getSync('d')).toBe(1);
        expect(warn).toHaveBeenCalledOnce();
        warn.mockRestore();
    });

    it('clear() empties values and waiters', () => {
        const m = new DeferredMap<string, number>();
        m.set('e', 1);
        m.clear();
        expect(m.has('e')).toBe(false);
        expect(m.getSync('e')).toBeUndefined();
    });
});
```

- [ ] **Step 2: Run — expect GREEN**

```bash
npm run test -- deferred
```

Expected: `deferred.test.ts` — 6 tests pass.

- [ ] **Step 3: Commit**

```bash
git add client/src/lib/utils/deferred.test.ts
git commit -m "test(client): add DeferredMap unit tests"
```

---

### Task 4: `SortHeader` component render + interaction test

The one component test — proves `@testing-library/svelte` + jsdom render a Svelte 5 runes component and that its `onclick` prop fires. `SortHeader` is 7 lines, non-canvas, minimal props (`{ label, onclick }`), rendering `<button>{label}</button>`.

**Files:**
- Create: `client/src/lib/components/SortHeader.test.ts`
- Consumes (existing, do not modify): `client/src/lib/components/SortHeader.svelte` — `let { label, onclick }: { label: string; onclick: (e: unknown) => void } = $props();`, template `<button ... onclick={onclick}>{label}</button>`.

**Interfaces:**
- Consumes the harness from Task 1. Adds one `*.test.ts` file. No state mutation in the component, so no `flushSync`/`$effect.root` needed (those caveats apply to future stateful component tests).

- [ ] **Step 1: Write `client/src/lib/components/SortHeader.test.ts`**

```ts
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import SortHeader from './SortHeader.svelte';

describe('SortHeader', () => {
    it('renders the label inside a button', () => {
        render(SortHeader, { props: { label: 'Name', onclick: vi.fn() } });
        const button = screen.getByRole('button', { name: 'Name' });
        expect(button).toBeInTheDocument();
    });

    it('calls onclick when the button is clicked', async () => {
        const onclick = vi.fn();
        render(SortHeader, { props: { label: 'Name', onclick } });
        await fireEvent.click(screen.getByRole('button', { name: 'Name' }));
        expect(onclick).toHaveBeenCalledTimes(1);
    });
});
```

- [ ] **Step 2: Run — expect GREEN**

```bash
npm run test -- SortHeader
```

Expected: `SortHeader.test.ts` — 2 tests pass. (The button's accessible name normalizes the template whitespace to `"Name"`, so `getByRole('button', { name: 'Name' })` matches.)

- [ ] **Step 3: Run the full suite once**

```bash
npm run test
```

Expected: **4 files, 20 tests, all pass** (vec2 6 + matrix 6 + deferred 6 + SortHeader 2).

- [ ] **Step 4: Commit**

```bash
git add client/src/lib/components/SortHeader.test.ts
git commit -m "test(client): add SortHeader component render + interaction test"
```

---

### Task 5: `client-ci.yml` — minimal green gate on node 24

**Files:**
- Create: `.github/workflows/client-ci.yml` (repo root)
- Consumes: `client/.nvmrc` (Task 1), `client/package-lock.json`, and the `verify:runes`/`test`/`build` scripts.

**Interfaces:**
- Produces the `Client CI` workflow. Later phases append `format:check` (P2), `lint` (P3), `check` (P4) steps in that order.

- [ ] **Step 1: Create `.github/workflows/client-ci.yml`**

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
```

- [ ] **Step 2: Sanity-check the workflow locally (mirror the CI steps under node 24)**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/frontend-ci-testing/client
. "$HOME/.nvm/nvm.sh" && nvm use 24
npm ci
npm run verify:runes
npm run test
npm run build
```

Expected: `verify:runes` exits 0 (no legacy `export let`), `test` = 20 passing, `build` succeeds. (`npm ci` reinstalls from the committed lockfile — proves CI's clean install works. Note: `node-version-file` and `cache-dependency-path` are resolved from the repo root, hence the `client/` prefix even though steps run in `client/`.)

- [ ] **Step 3: Commit**

```bash
cd /home/kdatta/workspace/eyened-platform-worktrees/frontend-ci-testing
git add .github/workflows/client-ci.yml
git commit -m "ci(client): add Client CI gate (verify:runes/test/build) on node 24"
```

- [ ] **Step 4: (When ready to open the PR) push and verify the gate runs green**

```bash
git push -u origin feature/frontend-ci-testing
# Open a PR into `development`; confirm the "Client CI" check runs and passes.
```

Expected: the `Client CI` check appears on the PR and is green. **Exit criteria for Phase 1 met** when it does. (Making it a *required* check is the separate manual admin step documented under *Enabling enforcement* in the spec — out of scope here.)

---

## Self-Review

**Spec coverage (Phase 1 section of the design spec):**
- Test devDeps (vitest/TL-svelte/jest-dom/jsdom) → Task 1 Step 3. ✅
- `vite.config.ts` test block + `VITEST`-guarded `resolve.conditions` → Task 1 Step 6. ✅
- `vitest-setup.ts` (jest-dom + TL cleanup) → Task 1 Step 5. ✅
- `test`/`test:watch` scripts → Task 1 Step 4. ✅
- Unit tests `vec2`/`matrix`/`utils/deferred` → Tasks 1/2/3. ✅
- One simple component render → Task 4 (`SortHeader`). ✅
- `.nvmrc` = 24 + `engines.node >= 24` → Task 1 Steps 2/4. ✅
- `client-ci.yml` with `verify:runes`/`test`/`build` on node 24 → Task 5. ✅
- Exit criteria: `client-ci` green + `test`/`build` confirmed under node 24 → Task 1 Steps 9–10, Task 5 Steps 2/4. ✅

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N" — every step has concrete code or an exact command with expected output. ✅

**Type/name consistency:** Production APIs referenced in tests (`Vec2`/`vec2`, `Matrix`/`from_translate_scale`/`fromRows`/`inverse`/`getMatrixFromPointSets`, `DeferredMap.get/getSync/set/has/clear`, `SortHeader` props `{ label, onclick }`) match the read source. The `test` script name is used identically in Tasks 1–5 and the workflow. Config keys (`environment`/`globals`/`setupFiles`/`conditions`) match the spec's Vitest snippet. ✅

**Scope note:** Formatting (`prettier`) and type-check (`svelte-check`) are intentionally excluded — test files are not lint/type-gated in Phase 1; Phase 2 reformats them and Phase 4 owns `check`. `tsconfig.json` is deliberately untouched (jest-dom types are pulled in per-file via `import '@testing-library/jest-dom/vitest'` in the component test).
