# Follow-ups from Frontend CI Phase 3 — ESLint gate

- **Source:** Phase 3 plan + `svelte5-best-practices` review (2026-07-16) — [plan](../superpowers/plans/2026-07-16-frontend-ci-phase3-eslint.md), [design](../superpowers/specs/2026-07-09-frontend-ci-testing-design.md).
- **Context:** Phase 3 lands the ESLint gate green by grandfathering three high-volume rules into a ratcheting `eslint-suppressions.json` baseline — enforced on **new** code, existing occurrences tolerated. These are the ratchet-down items plus findings from the Svelte-5 review. See `client/docs/eslint-ratchet.md` for the prune workflow.

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
