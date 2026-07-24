# Frontend CI Phase 3 — ESLint flat config → green (with ratcheting baseline)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the ESLint gate step (`npm run lint`) in `client-ci.yml` **green**, on a modern eslint-10 flat config, enforcing every valuable rule on new code while grandfathering the three large judgment-heavy backlogs into a ratcheting `eslint-suppressions.json` baseline.

**Architecture:** Replace the dead `.eslintrc.cjs` (eslint 8, extends a never-installed config) with `eslint.config.js` (flat, eslint 10). Reach a green `eslint .` not by mass-rewriting but by a deliberate **per-rule policy**: *fix now* the small/mechanical/defect rules so they are clean; *suppress + enforce* only `no-explicit-any` (353), `require-each-key` (51), `prefer-svelte-reactivity` (28) via ESLint's native bulk-suppressions (count-per-file baseline that fails on any new violation and ratchets down via `--prune-suppressions`). The gate command stays plain `eslint .` — it auto-reads the suppressions file.

**Tech Stack:** eslint 10.7, typescript-eslint 8.64, eslint-plugin-svelte 3.20 + svelte-eslint-parser 1.8, @eslint/js 10, eslint-config-prettier 10.1, globals 17. SvelteKit 5 (runes), Vite 6, node 24.

## Global Constraints

- **Node 24** — gate runs on `client/.nvmrc` (`24`); local dev matches. Already in place from Phase 1.
- **Exact devDep versions (already installed into `client/package.json`; do not change):** `eslint@^10.7.0`, `@eslint/js@^10.0.1`, `typescript-eslint@^8.64.0`, `eslint-plugin-svelte@^3.20.0`, `svelte-eslint-parser@^1.8.0`, `eslint-config-prettier@^10.1.8`, `globals@^17.7.0`. The old `eslint@^8`, `eslint-config-prettier@^8`, and `eslint-plugin-svelte@^2` (was in `dependencies`) are already removed.
- **Flat config only.** eslint 10 does not read `.eslintrc.*`. Ignores live in a `{ ignores: [...] }` block in `eslint.config.js`, **not** `.eslintignore`.
- **Ignores are derived from the Makefile generator outputs, NOT filename prefixes.** Only `src/types/openapi.ts` (gen-types) and `src/types/openapi.json` (gen-openapi) are generated. `src/types/openapi_types.ts`, `src/types/openapi_constants.ts`, and the `*.d.ts` in that dir are **hand-written and MUST stay linted.**
- **`lint` = `eslint . && prettier --check .`** (consolidated static-quality check). It **replaces** Phase 2's separate `format:check` CI step, so prettier runs exactly once. Two scripts, two jobs: `lint` (check — used by CI) and `lint:fix` = `eslint . --fix && prettier --write .` (fix — local). The now-redundant `format`/`format:check` scripts are **deleted**. Editor lint-on-save is independent of all of these — it is driven by the ESLint/Prettier extensions reading `eslint.config.js`/`.prettierrc` + `.vscode/settings.json` (see Appendix), so the on-save goal is unaffected.
- **CI steps run fail-fast — cheapest / most-common-failure first.** Final order: `verify:runes` (grep, instant) → `lint` (static, few s) → `test` (vitest, s) → `build` (vite, ~28s, last). This **reorders** the Phase 1/2 steps (which ran `test`/`build` ahead of the static checks).
- **Suppressions via `--suppress-rule` for exactly the 3 backlog rules, never `--suppress-all`.** `--suppress-all` would grandfather *any* residual violation and silently hide a regression in a fix-now rule. Per-rule suppression keeps every other rule hard-failing.
- **Unpruned suppressions stay STRICT — do NOT pass `--pass-on-unpruned-suppressions`.** *(Controller-verified empirically against the installed eslint 10.7.0, not assumed.)* When a contributor **fixes** an existing suppressed violation, the baseline count goes stale and `eslint .` **exits 2** with: `There are suppressions left that do not occur anymore. To resolve this, re-run the command with --prune-suppressions`. That is CI going red *for improving the code* — surprising, but it is the only mechanism that makes the ratchet actually ratchet. With the flag, the baseline becomes a floor that never lowers and "the baseline only shrinks" becomes unenforceable. The failure is self-documenting (the message names the exact fix), so accept it and **document it prominently** in `eslint-ratchet.md`. Note the exit code is **2, not 1** — the same error-vs-differ trap that bit Phase 2.
- **Verified suppression semantics (controller, empirical — do not re-derive):** baseline generates to exactly **432 across 88 files** = 353 + 51 + 28. Adding a violation to an **already-suppressed** file correctly **exits 1** and reports it (counts ratchet per file; a suppressed file is NOT blanket-exempt). Removing one → exit 2 per above.
- **Every task that edits source MUST re-verify `prettier --check .`.** Prettier has been a live CI gate since Phase 2, and eslint remediation (renaming identifiers, rewriting expressions) changes line widths — this is precisely the edit class that breaks formatting. Tasks 2–4 omitted this check and Task 2 shipped a prettier-dirty file that made `client-ci` red at 173e143 (fixed in `1bbef06`). Do not repeat.
- **The CI `lint` step is added only once `npm run lint` exits 0 locally** — so `client-ci` is never red (phase invariant). "Added when green" is about *when in the phase sequence* the step lands, not its position in the job (fail-fast puts `lint` between `verify:runes` and `test`).
- DRY, YAGNI, frequent commits. Intermediate commits within this phase MAY be red (the gate step is not added until the end); the phase's PR is green only at the final commit.

## Measured baseline (this HEAD, eslint 10 flat config)

`npx eslint .` → **579 errors, 0 warnings, 0 parse errors**, 138/464 files. Only **9 auto-fixable**. The `.svelte.ts` parser wiring is validated (0 parse errors). Rule breakdown and disposition:

| Rule | N | Disposition |
|---|---|---|
| `@typescript-eslint/no-explicit-any` | 353 | **suppress + enforce** |
| `@typescript-eslint/no-unused-vars` | 64 | fix now (config `^_` + delete dead) — Task 2 |
| `svelte/require-each-key` | 51 | **suppress + enforce** |
| `svelte/prefer-svelte-reactivity` | 28 | **suppress + enforce** |
| `svelte/no-navigation-without-resolve` | 18 | fix now (adopt `resolve()`) — Task 4 |
| `svelte/no-unused-svelte-ignore` | 17 | fix now — Task 3 |
| `no-useless-assignment` | 17 | fix now — Task 3 |
| `prefer-const` | 9 (6 fix) | fix now (autofix) — Task 3 |
| `no-var` | 5 (3 fix) | fix now (autofix) — Task 3 |
| `svelte/no-useless-children-snippet` | 3 | fix now — Task 3 |
| `svelte/prefer-writable-derived` | 2 | fix now — Task 3 |
| `no-empty` | 2 | fix now — Task 3 |
| `no-case-declarations` | 2 | fix now — Task 3 |
| `svelte/no-at-html-tags` | 2 | fix now (inline-disable, trusted) — Task 3 |
| `@typescript-eslint/no-this-alias` | 1 | fix now — Task 3 |
| `@typescript-eslint/no-unsafe-function-type` | 1 | fix now — Task 3 |
| `@typescript-eslint/no-empty-object-type` | 1 | fix now — Task 3 |
| `@typescript-eslint/no-unused-expressions` | 1 | fix now — Task 3 |
| `svelte/no-dom-manipulating` | 1 | fix now — Task 3 |
| `no-prototype-builtins` | 1 | fix now — Task 3 |

Suppressed backlog after fix-now = **432** (353 + 51 + 28).

---

## File Structure

- **Create** `client/eslint.config.js` — flat config: ignores (Makefile-derived), `@eslint/js` recommended, `typescript-eslint` recommended (non-type-aware), `eslint-plugin-svelte` flat recommended + TS parser wired into `.svelte`/`.svelte.ts`/`.svelte.js`, `no-unused-vars` `^_` ignore config, the ported `export let` guard, `eslint-config-prettier/flat` last.
- **Create** `client/eslint-suppressions.json` — generated baseline for the 3 backlog rules (committed).
- **Delete** `client/.eslintrc.cjs`, `client/.eslintignore` (empty).
- **Modify** `client/package.json` — add `lint` + `lint:fix`; **delete** the redundant `format`/`format:check` (devDeps already updated).
- **Modify** `.github/workflows/client-ci.yml` — replace the `format:check` step with `lint`, and reorder steps fail-fast (`verify:runes` → `lint` → `test` → `build`).
- **DEFERRED — do NOT create** `client/.vscode/settings.json` / `extensions.json` (Appendix). Editor lint-on-save is a separate follow-up per the user's decision. Task 5 must not create these files.
- **Modify** source files under `client/src/` — remediation for the fix-now rules (Tasks 2–4).
- **Create** `client/docs/eslint-ratchet.md` (or a `## ESLint` section in `client/README.md`) — how the suppressions baseline works and how to ratchet it down.

**Per-rule verification helper (used throughout).** From `client/`:

```bash
# Count remaining violations of a rule (stylish output prints the rule id at line end):
npx eslint . 2>/dev/null | grep -c '<rule-id>'   # e.g. @typescript-eslint/no-unused-vars
# Full remaining total:
npx eslint . 2>/dev/null | grep -cE '  (error|warning)  '
```

---

## Task 1: Flat-config foundation (config loads; still red — expected)

**Files:**
- Create: `client/eslint.config.js`
- Delete: `client/.eslintrc.cjs`, `client/.eslintignore`
- Verify against: `client/package.json` (devDeps already updated), `client/svelte.config.js`

**Interfaces:**
- Produces: a loadable flat config. `eslint .` runs to completion (exit 1 with rule violations, **no config/parse crash**). Later tasks drive the violation count to a suppressible state.

- [ ] **Step 1: Write `client/eslint.config.js`**

```js
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import svelte from "eslint-plugin-svelte";
import prettier from "eslint-config-prettier/flat";
import globals from "globals";
import svelteConfig from "./svelte.config.js";

export default tseslint.config(
    {
        // Ignores derived from the Makefile generator outputs (gen-openapi ->
        // openapi.json, gen-types -> openapi.ts) plus framework build output.
        // Hand-written files under src/types/ (openapi_types.ts,
        // openapi_constants.ts, *.d.ts) are intentionally NOT ignored.
        ignores: [
            ".svelte-kit/",
            "build/",
            "dist/",
            "node_modules/",
            "src/types/openapi.ts",
            "src/types/openapi.json",
        ],
    },
    js.configs.recommended,
    ...tseslint.configs.recommended,
    ...svelte.configs.recommended,
    {
        languageOptions: {
            globals: { ...globals.browser, ...globals.node },
        },
        rules: {
            // Required signature params / intentional unused → prefix with `_`.
            "@typescript-eslint/no-unused-vars": [
                "error",
                {
                    argsIgnorePattern: "^_",
                    varsIgnorePattern: "^_",
                    caughtErrorsIgnorePattern: "^_",
                    destructuredArrayIgnorePattern: "^_",
                },
            ],
        },
    },
    {
        // Wire the TS parser into .svelte <script lang="ts"> blocks AND the
        // *.svelte.ts / *.svelte.js rune-module extensions.
        files: ["**/*.svelte", "**/*.svelte.ts", "**/*.svelte.js"],
        languageOptions: {
            parserOptions: {
                parser: tseslint.parser,
                extraFileExtensions: [".svelte"],
                svelteConfig,
            },
        },
    },
    {
        // Ported from the legacy .eslintrc.cjs: forbid `export let` in runes mode.
        files: ["**/*.svelte"],
        rules: {
            "no-restricted-syntax": [
                "error",
                {
                    selector: "ExportNamedDeclaration[declaration.kind='let']",
                    message:
                        "Use $props() instead of `export let` in runes mode.",
                },
            ],
        },
    },
    prettier,
);
```

- [ ] **Step 2: Delete the dead legacy config**

```bash
git rm client/.eslintrc.cjs client/.eslintignore
```

- [ ] **Step 3: Verify the config loads (no crash) and parses cleanly**

Run: `cd client && npx eslint . 2>/tmp/eslint-err.txt >/dev/null; echo "exit=$?"; cat /tmp/eslint-err.txt`
Expected: `exit=1` (rule violations), **empty stderr** (no config/flat-config error, no parse errors).

- [ ] **Step 4: Verify no parse/fatal messages**

Run: `cd client && npx eslint . -f json | node -e 'let n=0;for(const f of JSON.parse(require("fs").readFileSync(0)))for(const m of f.messages)if(m.fatal||m.ruleId===null)n++;console.log("parse/fatal:",n)'`
Expected: `parse/fatal: 0`

- [ ] **Step 5: Commit**

```bash
git add client/eslint.config.js client/package.json client/package-lock.json
git commit -m "build(client): replace dead eslintrc with eslint 10 flat config

Adds the eslint-10 flat-config toolchain (typescript-eslint, eslint-plugin-svelte 3,
eslint-config-prettier flat) and eslint.config.js. TS parser wired for .svelte/.svelte.ts.
Ignores derive from the Makefile generator outputs (openapi.ts/json) only; hand-written
src/types/* stay linted. Gate step NOT added yet (config is still red)."
```

---

## Task 2: `@typescript-eslint/no-unused-vars` → 0

**Files:**
- Modify: source files under `client/src/` flagged by the rule (~64 sites; the `^_` config in Task 1 already resolves required-param cases).

**Interfaces:**
- Consumes: the `no-unused-vars` `^_` config block from Task 1.
- Produces: 0 `@typescript-eslint/no-unused-vars` violations.

- [ ] **Step 1: List remaining sites after the `^_` config**

Run: `cd client && npx eslint . 2>/dev/null | grep '@typescript-eslint/no-unused-vars'`
This is the working list. Two fix modes per site:
- **Genuinely dead** (unused local `const`/`let`, unused import, unused destructure): **delete** it.
- **Required by signature / intentional** (event handler param, interface-mandated arg): **rename with a leading `_`** (e.g. `event` → `_event`) so the config ignores it. Do NOT delete params that a caller/framework passes positionally.

- [ ] **Step 2: Apply fixes** file-by-file per Step 1's list, choosing delete-vs-`_`-prefix per the rule above. No behavior change.

- [ ] **Step 3: Verify the rule is clean**

Run: `cd client && npx eslint . 2>/dev/null | grep -c '@typescript-eslint/no-unused-vars'`
Expected: `0`

- [ ] **Step 4: Verify no functional regression** (types + tests still pass — this task deletes/renames identifiers)

Run: `cd client && npm run test && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -3`
Expected: tests pass; **svelte-check error count is not higher than the pre-task count** (Phase 4 owns svelte-check green; here we only guard against *introducing* new type errors by deleting a used symbol).

- [ ] **Step 5: Commit**

```bash
git add -A client/src
git commit -m "refactor(client): remove dead bindings; guard intentional unused with _ (no-unused-vars)"
```

---

## Task 3: Mechanical tail → 0 (autofix + small rules + trusted inline-disables)

**Files:**
- Modify: source files flagged by `prefer-const`, `no-var`, `no-empty`, `no-case-declarations`, `no-prototype-builtins`, `no-useless-assignment`, `no-unused-svelte-ignore`, `svelte/no-useless-children-snippet`, `svelte/prefer-writable-derived`, `svelte/no-dom-manipulating`, `@typescript-eslint/no-this-alias`, `@typescript-eslint/no-unsafe-function-type`, `@typescript-eslint/no-empty-object-type`, `@typescript-eslint/no-unused-expressions`, `svelte/no-at-html-tags`.

**Interfaces:**
- Produces: 0 violations for every rule listed above.

- [ ] **Step 1: Apply autofixes**

Run: `cd client && npx eslint . --fix`
This clears the 6 `prefer-const` + 3 `no-var` auto-fixables (and any other safe fixes). Review the diff — it must be behavior-preserving.

- [ ] **Step 2: Fix the remaining mechanical rules by hand**, per rule:
  - `no-var` (remaining) → `let`/`const`. `prefer-const` (remaining) → `const`.
  - `no-empty` → add a comment or remove the empty block. `no-case-declarations` → wrap the `case` body in `{ }`. `no-prototype-builtins` → `Object.prototype.hasOwnProperty.call(obj, k)` (or `Object.hasOwn`).
  - `no-useless-assignment` → drop the dead assignment. **Exception:** bits-ui/shadcn `let ref = ...` bindable-prop patterns are false positives — add `// eslint-disable-next-line no-useless-assignment -- bindable prop, value read via binding` at those sites.
  - `no-unused-svelte-ignore` → delete the stale `<!-- svelte-ignore ... -->` comment.
  - `svelte/no-useless-children-snippet` → remove the redundant `children` snippet. `svelte/prefer-writable-derived` → convert `$state` + `$effect` write-back to `$derived.by`/writable-derived per the rule's message. `svelte/no-dom-manipulating` → replace direct DOM mutation with bound state (or disable-with-reason if genuinely required).
  - `@typescript-eslint/no-this-alias` → use an arrow fn or rename per message. `no-unsafe-function-type` → replace bare `Function` with a concrete signature. `no-empty-object-type` → replace `{}` type with `object`/`Record<string, unknown>`/`unknown`. `no-unused-expressions` → remove or make the expression a statement.
  - `svelte/no-at-html-tags` (2 sites: `DataTable.svelte:17`, `PanelRendering.svelte:45`) → these render **trusted** content; add `<!-- eslint-disable-next-line svelte/no-at-html-tags -- trusted, non-user content -->` above each `{@html}` after confirming the source is not user-supplied.

- [ ] **Step 3: Verify every tail rule is clean**

Run:
```bash
cd client && npx eslint . 2>/dev/null | grep -cE 'prefer-const|no-var|no-empty|no-case-declarations|no-prototype-builtins|no-useless-assignment|no-unused-svelte-ignore|no-useless-children-snippet|prefer-writable-derived|no-dom-manipulating|no-this-alias|no-unsafe-function-type|no-empty-object-type|no-unused-expressions|no-at-html-tags'
```
Expected: `0`

- [ ] **Step 4: Verify no regression**

Run: `cd client && npm run test && npm run build`
Expected: tests pass; build succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A client/src
git commit -m "refactor(client): clear mechanical eslint rules (const/var/empty/svelte-ignore/etc.)"
```

---

## Task 4: Adopt `resolve()` — `svelte/no-navigation-without-resolve` → 0

**Files (18 sites, 8 files):**
- `src/lib/browser/StudyBlock.svelte:82,93` (href)
- `src/lib/browser/browserContext.svelte.ts:419,559,571,584` (goto — query-only `?${params}`)
- `src/lib/components/Main.svelte:19` (goto)
- `src/lib/components/ui/button/button.svelte:66` (href)
- `src/lib/tasks/TaskNameCell.svelte:10` (href)
- `src/lib/usermanager.svelte.ts:33,57,59,73,75,88` (goto)
- `src/lib/viewer-window/BrowserOverlay.svelte:87` (goto)
- `src/routes/tasks/[taskid]/+page.svelte:60,107` (goto)

**Interfaces:**
- Consumes: `resolve` from `$app/paths` (confirmed exported by `@sveltejs/kit` 2.22 — `runtime/app/paths/client.js`).
- Produces: 0 `svelte/no-navigation-without-resolve` violations, rule stays a **clean error** (no suppression).

- [ ] **Step 1: Classify each site** as **path navigation** vs **query/hash-only navigation** by reading its line.
  - **Path** (a route path or route id, e.g. `goto('/tasks')`, `<a href="/browser">`): resolvable.
  - **Query/hash-only** (same route, only search params/hash change, e.g. `goto(\`?${params.toString()}\`)`): `resolve()` takes a *route*, so a bare `?query` has no route to resolve.

- [ ] **Step 2: Fix path navigations with `resolve()`**

Pattern (`.ts`/`.svelte.ts`):
```ts
import { resolve } from "$app/paths";
// ...
goto(resolve("/tasks"));                 // was: goto("/tasks")
goto(resolve("/tasks/[taskid]", { taskid })); // parameterized route
```
Pattern (`.svelte` markup href):
```svelte
<script lang="ts">
    import { resolve } from "$app/paths";
</script>
<a href={resolve("/browser")}>…</a>       <!-- was: href="/browser" -->
```

- [ ] **Step 3: Handle query/hash-only navigations** — these stay same-route; `resolve()` does not apply. Add a justified inline disable:
```ts
// eslint-disable-next-line svelte/no-navigation-without-resolve -- query-only nav on current route
goto(`?${params.toString()}`);
```
(If the codebase prefers, `goto(\`${page.url.pathname}?${params}\`)` is an alternative, but the inline-disable is the minimal honest fix for a same-route query change.)

- [ ] **Step 4: Verify the rule is clean**

Run: `cd client && npx eslint . 2>/dev/null | grep -c 'svelte/no-navigation-without-resolve'`
Expected: `0`

- [ ] **Step 5: Verify navigation still works** (build + smoke the affected flows)

Run: `cd client && npm run build`
Expected: build succeeds. (Manual smoke of task/browser navigation is ideal if a dev server is available; the resolve() rewrites are behavior-preserving for an empty base path.)

- [ ] **Step 6: Commit**

```bash
git add -A client/src
git commit -m "refactor(client): route navigation through resolve() ($app/paths)

Adopts SvelteKit resolve() for all path-based goto()/href, keeping
svelte/no-navigation-without-resolve enforced clean. Query-only same-route
navigations carry a justified inline-disable."
```

---

## Task 5: Suppress the 3 backlog rules + wire the gate green

**Files:**
- Create: `client/eslint-suppressions.json` (generated, committed)
- Modify: `client/package.json` (add `lint` + `lint:fix`; delete `format`/`format:check`)
- Modify: `.github/workflows/client-ci.yml` (replace `format:check` step with `lint`; reorder fail-fast)
- Create: `client/docs/eslint-ratchet.md`

**Interfaces:**
- Consumes: a tree where every fix-now rule (Tasks 2–4) reports 0.
- Produces: `npm run lint` exits 0; `client-ci` gains a green `lint` step.

- [ ] **Step 1: Confirm only the 3 backlog rules remain**

Use the **JSON formatter**, not stylish+grep. (The earlier `grep -oE '[a-z@/-]+$'` recipe is unreliable: it also matches the file-path header lines that stylish prints — `…/foo.svelte` → `svelte` — polluting the very tally that guards against suppressing an unintended rule.)

```bash
cd client && npx eslint . -f json 2>/dev/null > /tmp/eslint.json; node -e '
const rs=JSON.parse(require("fs").readFileSync("/tmp/eslint.json"));
const per={};let fatal=0;
for(const f of rs)for(const m of f.messages){if(m.fatal||m.ruleId===null)fatal++;per[m.ruleId]=(per[m.ruleId]||0)+1;}
console.log("parse/fatal:",fatal); console.log(per);'
```
Expected **exactly**: `{ "@typescript-eslint/no-explicit-any": 353, "svelte/require-each-key": 51, "svelte/prefer-svelte-reactivity": 28 }` and `parse/fatal: 0`. **If any other rule appears, go back and fix it — do not suppress it.** *(Controller confirmed this exact output at the Task 5 base commit.)*

- [ ] **Step 2: Generate the suppressions baseline for exactly those 3 rules**

Run:
```bash
cd client && npx eslint . \
  --suppress-rule @typescript-eslint/no-explicit-any \
  --suppress-rule svelte/require-each-key \
  --suppress-rule svelte/prefer-svelte-reactivity
```
This writes `client/eslint-suppressions.json` (count-per-file for those rules). It does **not** touch source.

- [ ] **Step 3: Verify `eslint .` is now green**

Run: `cd client && npx eslint . ; echo "exit=$?"`
Expected: no output, `exit=0`.

- [ ] **Step 4: Verify the ratchet actually blocks new violations** (prove the gate is not hollow)

Two probes. **Probe B is the important one** — a brand-new file failing proves little, since the real-world regression is a new `any` added to a file that is *already* in the baseline, where count-per-file suppression could plausibly have exempted the whole file.

```bash
# Probe A — brand-new file is not auto-exempt:
cd client && cat > src/lib/_ratchet_probe.ts <<'EOF'
export const probe = (x: any) => x;   // deliberate no-explicit-any
EOF
npx eslint src/lib/_ratchet_probe.ts; echo "exit=$?"   # EXPECT exit=1
rm src/lib/_ratchet_probe.ts

# Probe B — an ALREADY-SUPPRESSED file rejects one MORE violation:
# Pick any file listed in eslint-suppressions.json, append a new `any`, and lint it.
# EXPECT exit=1 naming the added line. Revert the edit afterwards (git checkout -- <file>).
```
Expected: both `exit=1`. Confirms new code is enforced despite the baseline, and that suppression is a per-file *count* that ratchets — not a blanket file exemption. **Leave no probe artifacts behind** (`git status` must be clean of them before Step 10).

- [ ] **Step 5: Update `client/package.json` scripts** — add `lint`/`lint:fix`, and **delete** the now-redundant `format`/`format:check`:
```json
"lint": "eslint . && prettier --check .",
"lint:fix": "eslint . --fix && prettier --write ."
```
Remove the existing `"format": "prettier --write ."` and `"format:check": "prettier --check ."` entries — `lint`/`lint:fix` subsume them.

- [ ] **Step 6: Verify `npm run lint`** (now runs eslint **and** prettier --check)

Run: `cd client && npm run lint; echo "exit=$?"`
Expected: `exit=0` (eslint green via suppressions; prettier already clean from Phase 2).

- [ ] **Step 7: Write `client/docs/eslint-ratchet.md`**

```markdown
# ESLint ratcheting baseline

`npm run lint` runs `eslint . && prettier --check .` (flat config, `eslint.config.js`).
Every rule is enforced on **new** code. Three high-volume backlogs are grandfathered in
`eslint-suppressions.json` (count-per-file): `@typescript-eslint/no-explicit-any`,
`svelte/require-each-key`, `svelte/prefer-svelte-reactivity`.

## Rules
- **The baseline only shrinks.** Never run `eslint --suppress-all` or
  `--suppress-rule` to hide a *new* violation. Fix new violations instead.
- Adding a genuinely-unavoidable new violation requires an inline
  `// eslint-disable-next-line <rule> -- <reason>`, reviewed in the PR — not a
  suppressions-file edit. **A disable's stated reason must be true of the code**,
  not an aspiration — prefer making it true by construction (e.g. a type that
  enforces it) over asserting it in prose.

## "But I FIXED an `any` and CI went red!"
That is expected, and it is the ratchet working. Removing a suppressed violation
leaves a stale count, and `eslint .` fails with:

> There are suppressions left that do not occur anymore. To resolve this, re-run
> the command with `--prune-suppressions` to remove unused suppressions.

**Fix:** `cd client && npx eslint . --prune-suppressions` and commit the updated
`eslint-suppressions.json` alongside your change. One extra command; it is what
keeps the baseline honest.

Note the exit code is **2** (error), not 1 (violations found) — so a script that
only tests `-eq 1` will misread it. We deliberately do NOT pass
`--pass-on-unpruned-suppressions`: it would keep CI green but let the baseline
become a floor that never lowers.

Two PRs that each prune will conflict in `eslint-suppressions.json`. It's JSON —
regenerate rather than hand-merge: take either side, then re-run `--prune-suppressions`.

## Limitation
Suppressions are counts per file, not per line: within an already-suppressed
file, removing one old violation and adding one new violation of the same rule
(net count unchanged) is not caught. Rare; still far better than disabling.
Adding a violation *without* removing one IS caught (count goes up → error).
```

- [ ] **Step 8: Reorder `.github/workflows/client-ci.yml` fail-fast and replace `format:check` with `lint`.** The steps block becomes exactly:
```yaml
      - run: npm ci
      - run: npm run verify:runes # export-let guard (grep, instant)
      - run: npm run lint         # eslint . && prettier --check . (+ suppressions ratchet)
      - run: npm run test         # vitest run
      - run: npm run build        # vite build (most expensive — last)
```
This **deletes** the standalone `- run: npm run format:check` step (its prettier check now lives inside `lint`) and moves the static checks (`verify:runes`, `lint`) ahead of the dynamic ones (`test`, `build`).

- [ ] **Step 9: Final verification — the whole gate green locally**

Run (in CI/fail-fast order):
```bash
cd client && npm run verify:runes && npm run lint && npm run test && npm run build; echo "exit=$?"
```
Expected: `exit=0` (every gate step green, in the same order CI runs them).

- [ ] **Step 10: Commit**

```bash
git add client/eslint-suppressions.json client/package.json client/docs/eslint-ratchet.md .github/workflows/client-ci.yml
git commit -m "ci(client): add eslint gate green with ratcheting suppressions baseline

lint = 'eslint . && prettier --check .' (consolidated; replaces the separate
format:check step). CI steps reordered fail-fast: verify:runes -> lint -> test ->
build. Every rule enforced on new code; 432 existing no-explicit-any/require-each-key/
prefer-svelte-reactivity violations grandfathered in eslint-suppressions.json and
ratcheted via --prune-suppressions. Gate step lands green (phase invariant)."
```

---

## Self-review checklist (run before execution)

1. **Spec coverage:** Phase 3 exit criterion ("`eslint .` clean; gate step green") → Task 5 Steps 3/6/9. `.svelte.ts` parser wiring → Task 1. `export let` guard ported → Task 1. Ignores from Makefile → Task 1 constraint. Deviations from the design (suppressions ratchet instead of blanket-disabling `no-explicit-any`; consolidated `lint` = `eslint . && prettier --check .` replacing the separate `format:check` step; fail-fast CI reorder) are recorded in Global Constraints — update the design doc's Phase 3 section to match after execution.
2. **Placeholder scan:** none — every fix rule names its concrete transform; per-site application (which identifier, which key) is legitimately execution-time discovery bounded by an exact site list.
3. **Type consistency:** rule ids are used verbatim from the measured baseline throughout; `resolve` import path (`$app/paths`) is confirmed against installed `@sveltejs/kit`.

## Open decision (flag before/while executing)

- **`no-unused-vars` (Task 2) fix-now vs suppress:** the plan fixes it (dead code is a defect, not style). If its 64 sites prove heavier than expected mid-task, it can be converted to the suppress-and-enforce bucket in one line (add `--suppress-rule @typescript-eslint/no-unused-vars` in Task 5 Step 2) rather than blocking the phase. Prefer fixing.

---

## Appendix — Editor lint-on-save (VS Code / Cursor) — ⛔ DEFERRED, NOT PART OF TASK 5

> **Do NOT implement this appendix.** The user deferred editor config to a later
> follow-up. It is recorded here only so the decision and the content aren't lost.
> Task 5 must not create `client/.vscode/`.

Independent of the CI gate and of the npm scripts. On-save is driven by the ESLint +
Prettier **extensions** reading `eslint.config.js` / `.prettierrc` directly, plus a
committed `.vscode/`. `eslint-config-prettier` (in `eslint.config.js`) is what stops the
two from fighting on save. Include this in Task 5's commit, or defer to a follow-up — it
does not affect the gate either way.

**`client/.vscode/extensions.json`** (recommend the extensions to contributors):
```json
{
    "recommendations": ["dbaeumer.vscode-eslint", "esbenp.prettier-vscode"]
}
```

**`client/.vscode/settings.json`**:
```json
{
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.codeActionsOnSave": {
        "source.fixAll.eslint": "explicit"
    },
    "eslint.useFlatConfig": true,
    "eslint.validate": ["javascript", "typescript", "svelte"],
    "[svelte]": { "editor.defaultFormatter": "esbenp.prettier-vscode" }
}
```
- `formatOnSave` + Prettier as default formatter → format on every save.
- `source.fixAll.eslint: "explicit"` → ESLint auto-fixes fixable violations on save (it will **not** silence a suppressed-backlog rule — a new `any` still shows as an error, matching the gate).
- Scope `.vscode/` under `client/` so it applies to the frontend workspace without imposing editor config on the Python/root tree.
