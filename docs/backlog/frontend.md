# Frontend

ESLint ratchet: after fixing a suppressed violation run `cd client && npx eslint . --prune-suppressions` and commit `eslint-suppressions.json`; never hand-merge that file. Run svelte-check in the dev container (`docker exec -w /app/client <client container> npx svelte-check --tsconfig ./tsconfig.json --output machine`); as your own user `.svelte-kit` EACCES errors inflate the counts.

### Sanitize the `{@html}` cells in `DataTable.svelte`
- **Status:** open (security)
- **Source:** Frontend CI Phase 3, 2026-07-16
- **Problem:** `client/src/lib/utils/DataTable.svelte:18` renders `{@html cell}` from JSON fetched by `dataSources.ts` `loadDataSource()`, possibly from an absolute admin-configured URL. A malicious/compromised source gets script execution. The inline eslint-disable means lint will never flag it again.
- **Fix:** sanitize (e.g. DOMPurify), render as text, or restrict data sources to a trusted origin.

### Stop treating 403 as an expired session in the API client
- **Status:** open (blocks the admin UI)
- **Source:** PR #247 manual-test walkthrough, 2026-09-24
- **Problem:** `isUnauthorizedStatus` in `client/src/lib/api/client.ts` returns true for 401 and 403, so a 403 triggers `/auth/refresh`, a retry, and `redirectToLogin()`. `/api/admin/*` returns 403 to a logged-in non-admin, who is bounced to login instead of shown "forbidden". Same code on `feature/rbac-admin-client`.
- **Fix:** refresh and retry on 401 only; surface 403 to the caller. Update `apiInvoke.test.ts` accordingly.

### Fix Svelte 5 reactivity traps
- **Status:** open
- **Source:** Phase 3 ESLint gate + Phase 4 svelte-check triage
- **Problem:** 28 grandfathered `svelte/prefer-svelte-reactivity` (native `Set`/`Map`/`URLSearchParams` in stores, e.g. `browserContext.svelte.ts`) and 75 `state_referenced_locally` warnings (worst: `DataTable.svelte` 14, `InstanceComponent.svelte` 8, `ViewerWindow.svelte` 6) — UI that silently never updates.
- **Fix:** use `SvelteSet`/`SvelteMap`/`SvelteURLSearchParams` where read in markup (query-string builders are false positives); move reads into reactive contexts.

### Key the grandfathered `{#each}` blocks
- **Status:** open
- **Source:** Phase 3 ESLint gate
- **Problem:** 46 `svelte/require-each-key` suppressions; unkeyed eaches attach DOM/state/focus to the wrong item on reorder.
- **Fix:** key by stable identity, prioritising blocks with local state/inputs/components; never key by index.

### Ratchet down `@typescript-eslint/no-explicit-any`
- **Status:** open
- **Source:** Phase 3 ESLint gate
- **Problem:** 334 suppressed `any` sites (of 408 suppressions across 81 files, at HEAD 5039aff7).
- **Fix:** type them in batches, pruning suppressions each time.

### Gate svelte-check in CI (Phase 4)
- **Status:** open
- **Source:** Phase 4 root-cause pass, re-measured 2026-08-24 (91 errors / 102 warnings)
- **Problem:** `npm run check` is not in CI; errors are ~90 individual fixes, not generated-type drift (1 of 91). svelte-check 4.x has no suppression mechanism, and `npm run check` does not pass `--fail-on-warnings`.
- **Fix:** delete dead `src/lib/image-processing/_color-standardization.ts` (10 errors) and decide `src/lib/webgl/renderTexture.ts` with it (9 errors, its only importer is the dead file) first; then either fix the rest or build a per-file count ratchet parsing `--output machine`, validated against the `COMPLETED … N ERRORS` line. Decide explicitly whether the gate covers warnings.

### Fix the remaining svelte-check error clusters
- **Status:** open
- **Source:** Phase 4 triage
- **Problem:** `DoubleRangeSlider.svelte` 18 errors (11 implicit-any, 3 unbound `bind:this` `| undefined`, 3 undeclared `ondragmove`); 16 implicit-any params elsewhere; 16 missing null/unknown guards, some latent runtime `TypeError`s (e.g. `TopRowImages.svelte:57` `e.target.focus()`).
- **Fix:** type properly (not `any`, which grows the ESLint baseline); treat the guard group as bug candidates.

### Fix the prop bugs unmasked by the `ui/` prop helpers
- **Status:** open
- **Source:** Phase 3 review
- **Problem:** `client/src/lib/components/Pagination.svelte:34` passes `isVisible`, not a prop of `Pagination.Item` (silently dropped); `client/src/lib/tasks/SubtasksTable.svelte:104` passes `colspan="6"` (string, typed `number`).
- **Fix:** decide whether `isVisible` behaviour is needed (maybe covered by `Pagination.Link isActive`); `colspan={6}`.

### Remove small dead code
- **Status:** open
- **Source:** Phase 3 sweep
- **Problem:** `client/src/lib/viewer-window/icons/AV-Nicking.svelte` declares an inert `stroke` prop and has 0 callers; `client/src/routes/+layout.ts` and `routes/users/login/+page.ts` have no-op `load()`s.
- **Fix:** delete the component (or the prop); delete the `load()`s after checking SvelteKit route semantics.

### Decide `prefer-const` for `.svelte` files
- **Status:** open
- **Source:** Phase 3 ESLint gate
- **Problem:** typescript-eslint's `eslint-recommended` scopes to TS files, so `.svelte` misses `prefer-const`; enabling it reports 729 sites (~200 are `let { x } = $props()`, the documented runes idiom).
- **Fix:** an idiom decision: enable and fix/baseline, or leave off on purpose.

### Re-audit navigation if `kit.paths.base` is ever set
- **Status:** open (conditional)
- **Source:** Phase 3 ESLint gate
- **Problem:** query-only `goto()`s carry `svelte/no-navigation-without-resolve` disables that are correct only while `base === ''`. `resolve()` throws on raw `[...]` in a query string.
- **Fix:** when a base path is introduced, route those through `resolve()` and drop the disables.
