# Follow-ups from Frontend CI Phase 3 — ESLint gate

- **Source:** Phase 3 plan + `svelte5-best-practices` review (2026-07-16) — [plan](../superpowers/plans/2026-07-16-frontend-ci-phase3-eslint.md), [design](../superpowers/specs/2026-07-09-frontend-ci-testing-design.md).
- **Context:** Phase 3 lands the ESLint gate green by grandfathering three high-volume rules into a ratcheting `eslint-suppressions.json` baseline — enforced on **new** code, existing occurrences tolerated. These are the ratchet-down items plus findings from the Svelte-5 review.

---

## How the ratchet works

`npm run lint` (in `client/`) runs `eslint . && prettier --check .`. Every **configured** rule is enforced on new code — including inside files that already carry suppressions. The three rules below are grandfathered in `client/eslint-suppressions.json` as a **count per file**, so the baseline can only shrink.

**"I fixed an `any` and CI went red!"** — expected, and the ratchet working. Removing a suppressed violation leaves a stale count and `eslint .` fails with _"There are suppressions left that do not occur anymore."_ Fix: `cd client && npx eslint . --prune-suppressions`, and commit the updated `eslint-suppressions.json` with your change.

- The exit code there is **2** (error), not 1 (violations found) — a script testing `-eq 1` misreads it.
- We deliberately do **not** pass `--pass-on-unpruned-suppressions`: it would keep CI green but let the baseline become a floor that never lowers. (This is not theoretical — merging `development` into the Phase 3 branch removed 2 `any`s and pruned the baseline 432 → 430 automatically.)
- **Never hand-merge a conflict in `eslint-suppressions.json`** — take either side, then re-run `--prune-suppressions`. It's generated: eslint rewrites it in its own format on every prune, which is why it's in `.prettierignore`.
- Adding an unavoidable new violation needs an inline `// eslint-disable-next-line <rule> -- <reason>`, reviewed in the PR — not a suppressions-file edit. **A disable's stated reason must be true of the code**, not an aspiration; prefer making it true by construction (a type that enforces it) over asserting it in prose. Phase 3's review found two disables that failed this, each hiding a real bug.
- **Limitation:** counts are per file, not per line — within an already-suppressed file, removing one violation and adding another of the same rule (net count unchanged) is not caught. Adding one _without_ removing one **is** caught.

---

## 1. Ratchet down `@typescript-eslint/no-explicit-any` (353)

**Status:** open

**What:** Replace `any` with real types incrementally, running `npx eslint . --prune-suppressions` (in `client/`) after each batch so the baseline can only shrink.

**Why:** Typing debt — `any` erases type safety. Already enforced on new code; the 353 existing sites are tolerated until typed. Largest of the three backlogs; no rush, but it should trend to zero.

---

## 2. Triage `svelte/require-each-key` (51) — keyed-each reconciliation

**Status:** open

**What:** Add correct keys, e.g. `{#each items as item (item.id)}`. **Prioritize** each-blocks whose children hold local state, inputs, or components.

**Why:** Unkeyed `{#each}` uses index-based reconciliation, so on reorder/remove Svelte attaches DOM/state/focus to the wrong item. **Do not key by index to force green** — that defeats the rule. Needs per-loop domain knowledge (which field is the stable identity), which is why it was deferred rather than rushed.

---

## 3. Triage `svelte/prefer-svelte-reactivity` (28) — potential live reactivity bugs

**Status:** open

**What:** In `.svelte.ts` stores, replace native `Set`/`Map`/`URLSearchParams` with the Svelte reactive equivalents (`SvelteSet`/`SvelteMap`/`SvelteURLSearchParams`) **where the collection is read in markup**. Prioritize collections bound to UI (e.g. the `Set`s in `browserContext.svelte.ts`). Transient query-string builders (a `URLSearchParams` used only to build `goto('?…')`) are false positives — leave or inline-disable.

**Why:** Svelte 5 reactivity is proxy-based on `$state`; mutating a **native** `Set`/`Map` bypasses it entirely, so the UI can silently fail to update. This is **correctness, not style** — surfaced by the `svelte5-best-practices` review (which corrected the earlier read of this rule as a mere opinion).

---

## 4. Revisit `svelte/no-navigation-without-resolve` if a base path is introduced

**Status:** open

**What:** If `kit.paths.base` is ever set (app served under a subpath), audit navigation for base-aware `resolve()` and remove the query-only inline-disables at any site that becomes a resolvable route.

**Why:** Phase 3 adopted the rule and fixed all path navigations via `resolve()` from `$app/paths`; query-only same-route `goto()`s carry justified inline-disables that are correct **only while `base === ''`**. A future base path changes that.

**Related trap (verified):** `resolve()` throws `Missing parameter '<x>'` if a **raw** `[...]` appears in the query string — `resolve("/tasks/[taskid]?f=[abc]", { taskid: "7" })` throws. Every current call site is safe because `URLSearchParams.toString()` and `encodeURIComponent` both percent-encode brackets (`f=%5Babc%5D`). A future hand-built query string could reintroduce it.

---

## 5. `DataTable.svelte` renders un-sanitized external data via `{@html}` — XSS surface

**Status:** open · **Pre-existing** (not introduced by Phase 3) · _security_

**What:** `client/src/lib/utils/DataTable.svelte:17` renders each cell with `{@html cell}`. Provenance: `DataTable` ← `ExternalData.svelte:13` ← `dataSources.ts:12` `loadDataSource()` → `isAbsoluteUrl(url) ? fetch(url) : fetchApi(url)` → `.json()`. So the rendered HTML is **network-fetched JSON from a possibly-absolute, admin-configured external URL**, injected raw. Options: sanitize (e.g. DOMPurify), render as text where markup isn't needed, or constrain the data-source contract to a trusted origin.

**Why:** A compromised or malicious configured data source (or anything able to influence its response) achieves script execution in the app. Phase 3 gave this an inline `eslint-disable` to reach a green gate; the disable is now worded to state the risk honestly rather than assert "trusted". **Deferring the fix is deliberate — this is a data-contract/security change, not a lint change — but the disable means the linter will never raise it again, so it lives here instead.**

Note the contrast with the _genuinely_ trusted twin at `PanelRendering.svelte:45`, which renders hardcoded literals (`enface`/`axial`). Both once carried the identical comment "trusted, non-user content"; only one of them was true.

---

## 6. `prefer-const` is not enforced in `.svelte` files (729 sites)

**Status:** open

**What:** `eslint.config.js` enables `no-var`/`prefer-rest-params`/`prefer-spread` for `.svelte` (all at 0), but **not `prefer-const`**. Enabling it surfaces 729 violations — ~200 on `let { x } = $props()`, the canonical runes idiom. To adopt: enable for `.svelte`, then either fix or fold into the suppressions baseline.

**Why:** Root cause is upstream and easy to miss: typescript-eslint's `eslint-recommended` turns these four rules on but hard-scopes itself to `**/*.{ts,tsx,mts,cts}`, so `.svelte` silently missed all four (`.svelte.ts` matches `**/*.ts` and was covered). Three were free to close; `prefer-const` is a large idiom decision, not a lint cleanup. It compiles fine as `const` (verified on Svelte 5.55.1, including `$bindable`), so this is a style/scale call — but Svelte's own docs use `let`.

---

## 7. Small pre-existing defects noticed during the Phase 3 sweep

**Status:** open · all **pre-existing**, none introduced by Phase 3

- **`PanelRendering.svelte:52`** — the `{:else}` branch iterates `Object.entries(options)` (i.e. `{enface, axial}`), so it renders options named "enface"/"axial" instead of render modes; it should index `options[viewerContext.image.orientation]` like the `{#if}` branch does. Normally unreachable (`radio = true` by default). Flagged because Phase 3 touched that line (removing an unused `label` binding — a correct, behavior-preserving fix).
- **`AV-Nicking.svelte:3`** — `Props` still declares `stroke?: string`, but the component no longer destructures it and the markup hardcodes `stroke:#000000`. The prop was always inert. The component is also **orphaned (0 callers repo-wide)** — drop the dead member or delete the component.
- **`+layout.ts` / `users/login/+page.ts`** — `load()` is now an empty no-op (pre-existing dead code; Phase 3 only narrowed the signature). Deleting `load` entirely has SvelteKit route-semantics implications, so it was left alone.
