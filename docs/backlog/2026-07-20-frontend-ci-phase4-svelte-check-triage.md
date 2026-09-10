# Frontend CI Phase 4 — svelte-check triage

- **Source:** Phase 4 root-cause pass (2026-07-20) against worktree HEAD `8c5b495` — [design](../superpowers/specs/2026-07-09-frontend-ci-testing-design.md) § _Phase 4_.
- **Context:** The design defers `npm run check` (svelte-check) to Phase 4 and instructs "root-cause the 158 first (cheap): are they real type bugs or generated-type/stale-sync drift?" This is that measurement. **Nothing here is fixed** — Phase 4 is unexecuted; this records what it is actually made of so the phase can be scoped.

---

## Measured baseline

Re-measured 2026-08-24 on `development` @ `46853f47`:

```
COMPLETED 1414 FILES 91 ERRORS 102 WARNINGS 64 FILES_WITH_PROBLEMS
```

Errors live in **30 files**, warnings in **39**; the two sets overlap in 5, which is where `64 FILES_WITH_PROBLEMS` comes from. `64` is **not** the error-file count — an easy misread when scoping.

The design's `158 errors / 103 warnings` figure is stale: Phase 3's sweep took errors **158 → 93** as a side effect, and five weeks of unrelated merges have since drifted them to 91 / 102. Nothing here was fixed on purpose.

### Reproducing this (read before you trust a number)

`npm run check` runs `svelte-kit sync` first, which **writes** to `client/.svelte-kit` — and that directory is owned by `root` because the dev container bind-mounts the worktree. Running the check as your own user produces an `EACCES` flood that **inflates the counts with errors that do not exist**. Run it in the container:

```bash
docker exec -w /app/client eyened-platform-dev-kaustav-client-1 \
  npx svelte-check --tsconfig ./tsconfig.json --output machine
```

`--output machine` emits one line per diagnostic with **workspace-relative** paths, terminated by a `COMPLETED … N ERRORS N WARNINGS` summary line — cross-check any parsed total against that summary rather than trusting a parser.

---

## The design's root-cause hypothesis is wrong

The design expects the bulk to be **generated-type / stale-sync drift** (`src/types/openapi.ts`, `.svelte-kit`) — i.e. regenerate types and most errors evaporate. Measured: **exactly 1 of 91** errors carries that signature, at `src/routes/tasks/[taskid]/grade/[setid]/+page.svelte:24:11`, where `instanceIDs` is `string[]` vs `number[]`.

**Its message changed while the defect did not.** TypeScript reported it as `Two different types with this name exist, but they are unrelated` in July; today the same line reports `Type 'Promise<…>' is not assignable to type 'Promise<…>'`. Anyone grepping for the old phrase will wrongly conclude it was fixed — match on the file and line, not the wording.

**There is no regenerate-and-done available.** Phase 4 is ~90 individually-judged type fixes, not a type-sync operation. Scope Phase 4 accordingly — and note the design's own escape hatch ("sub-phase if the real count is large") applies.

---

## Error triage (91)

| # | Category | Count | Nature |
|---|---|---|---|
| 1 | Dead file `_color-standardization.ts` | 10 | Orphaned — **delete, don't fix** |
| 2 | `renderTexture.ts` overloads | 9 | All one shape; likely one root cause |
| 3 | Implicit-`any` parameters | 16 | Mechanical annotations |
| 4 | `possibly null/undefined` + `of type unknown` | 16 | Real missing guards |
| 5 | Generated-type drift | 1 | The hypothesis above |
| 6 | Scattered genuine type errors | 39 | Individually judged |

Concentration — the top 10 files hold **67** errors; the tail is 4 files with 2 and **16 files with exactly 1**:

| Errors | File |
|---|---|
| 18 | `src/lib/viewer-window/DoubleRangeSlider.svelte` |
| 10 | `src/lib/image-processing/_color-standardization.ts` |
| 9 | `src/lib/webgl/renderTexture.ts` |
| 6 | `src/lib/forms/schemaValidator.svelte.ts` |
| 5 | `src/lib/viewer-window/icons/PanelIcon.svelte` |
| 5 | `src/lib/viewer-window/MultiImageViewer.svelte` |
| 4 | `src/lib/viewer-window/panelForm/PanelForm.svelte` |
| 4 | `src/lib/matrix.ts` |
| 3 | `src/lib/viewer/tools/Registration.ts` |
| 3 | `src/lib/image-processing/CFImageProcessing.ts` |

---

## 1. Delete dead `src/lib/image-processing/_color-standardization.ts` (10 errors)

**Status:** open

**What:** Delete the file. Confirm first that `colorStandardization()` is genuinely unwanted rather than an unfinished feature someone intends to land.

**Why:** It is dead and **cannot ever have worked**: imported by nothing (`grep` across `src/` finds zero references; graphify shows it unconnected), and 9 of its 10 errors are `Cannot find name` for functions that do not exist anywhere — `histogram`, `binsToCDF`, `interp`, `getTargetHistograms`, `fs_lut`, `calculateMuSigma`, `Histogram`. The `_` prefix matches the repo's other dead artifact, `src/lib/webgl/glsl/_fs_render_layer_highlight.frag`.

**Do this before any baselining.** It is 11% of the error count and pure noise; grandfathering dead code into a baseline enshrines a number that can never be pruned by fixing real code.

---

## 2. `src/lib/webgl/renderTexture.ts` — 9 × `No overload matches this call`

**Status:** open

**What:** Root-cause as one item, not nine. Every error in the file is the same shape, suggesting a single wrong WebGL signature or texture-format union rather than nine independent defects.

**Why:** Best effort-to-error ratio in the whole set — plausibly ~10% of the backlog for one fix. Worth attempting first to size the rest.

**Coupled to item 1.** `renderTexture.ts`'s only importer anywhere in `client/src` is the dead `_color-standardization.ts:3`. Deleting that file per item 1 orphans this one too, so the pair is one decision: fix these 9 errors, or delete 19. Settle it before Phase 4 is scoped.

---

## 3. `src/lib/viewer-window/DoubleRangeSlider.svelte` — 18 errors (largest single file)

**Status:** open

**What:** Three clusters: 11 implicit-`any` params (`event`, `evt`, `node`, `lower`, `upper`, `which`, `x`, `handlerFn`), 3 × `HTMLDivElement | undefined` not assignable to `HTMLDivElement`, and 3 × `'ondragmove' does not exist in type HTMLAttributes<HTMLDivElement>` (a custom event needing declaration-merging into Svelte's attribute types).

**Why:** Mostly mechanical, but the `ondragmove` cluster needs a real typing decision, and the `| undefined` cluster is a genuine unbound-`bind:this` hazard, not a formality.

---

## 4. Implicit-`any` parameters (16) and missing null/unknown guards (16)

**Status:** open

**What:** Annotate the 16 implicit-`any` params; add guards for the 7 `is possibly 'null'/'undefined'` and 9 `of type 'unknown'` sites.

**Why:** The implicit-`any` group is mechanical. The guard group is **not** cosmetic — e.g. `TopRowImages.svelte:57` does `e.target.focus()` where `e.target` is `possibly 'null'` and lacks `focus`; that is a latent runtime `TypeError`. Treat these as bug candidates, not annotation chores.

**Overlap note:** annotating these adds explicit types, so it will not fight the `@typescript-eslint/no-explicit-any` ratchet — unless the annotation chosen is `any`, which would grow `eslint-suppressions.json`. Type them properly.

---

## 5. Warning triage (102) — three-quarters are latent reactivity bugs

**Status:** open

| Warning | Count | Note |
|---|---|---|
| `state_referenced_locally` | **75** | Svelte 5 reactivity trap — likely real bugs |
| `css_unused_selector` | 21 | Dead CSS; mostly `DataTable.svelte` |
| `a11y_label_has_associated_control` | 4 | Accessibility |
| `slot_element_deprecated` | 1 | Svelte 4 → 5 migration leftover |
| `non_reactive_update` | 1 | Value mutated but not `$state(...)` |

**What:** Triage the 75 `state_referenced_locally` warnings. Each means a `$state`/`$props` value was read outside a reactive context, so **the reference captures only the initial value and silently never updates**. Most-affected: `DataTable.svelte` (14 warnings), `InstanceComponent.svelte` (8), `ViewerWindow.svelte` (6), `TagEditForm.svelte` (5). Commonest subjects: `image` (11), `instance` (9), `segmentation` (7), `viewerWindowContext` (5), `study` (5).

**Why:** This is the same failure family as `svelte/prefer-svelte-reactivity` (28) already tracked in the [Phase 3 ESLint follow-ups](2026-07-16-frontend-ci-phase3-eslint-followups.md) — stale UI that shows first-render data forever. Being a *warning* undersells it; some fraction are user-visible bugs.

**Gate interaction — deliberate decision needed:** `npm run check` does **not** pass `--fail-on-warnings`, so all 102 warnings are invisible to CI even after Phase 4 lands. If Phase 4 baselines errors only, this 75-warning bug surface stays permanently unenforced and will grow. Decide explicitly whether the Phase 4 gate covers warnings; do not let it default silently.

---

## 6. Ratcheting Phase 4 instead of fixing 91 errors first

**Status:** open — evaluated 2026-07-20, not built

**What:** Land the `check` gate green immediately by grandfathering existing errors into a per-file count baseline (enforce on new code, tolerate existing), mirroring Phase 3's `eslint-suppressions.json`, then ratchet down via items 1–5.

**Why / feasibility:** **svelte-check 4.1.5 has no native suppression mechanism** — there is no equivalent of ESLint ≥9.24's `--suppress-rule`/`--prune-suppressions`; its full option set is `--workspace --output --watch --preserveWatchOutput --tsconfig --no-tsconfig --ignore --fail-on-warnings --compiler-warnings --diagnostic-sources --threshold`. A ratchet must therefore be **built**: a wrapper script parsing `--output machine` into per-file counts against a committed `svelte-check-baseline.json`.

Two properties make that viable: machine-output paths are already **workspace-relative** (a baseline written in the container works on a CI runner), and the `COMPLETED … N ERRORS` line gives an independent total to validate the parser against. That validation is mandatory, not optional — a parser whose regex silently matches nothing yields a permanently-green gate enforcing nothing, the same class of failure Phase 3's review caught in its lying `eslint-disable`s.

**Known limitation, identical to the ESLint ratchet:** per-file *counts*, not error *identity* — fixing one error in a 2-error file while introducing a different one keeps the count at 2 and passes. Pinning line numbers instead would churn the baseline on every unrelated edit.

**Prerequisite:** item 1 (delete the dead file) lands first, so the baseline starts at **81 errors / 29 files** rather than enshrining 10 undeletable phantoms — or **72 / 28** if item 2's `renderTexture.ts` goes with it, which it can, since the dead file is its only importer. Decide that pair before fixing the baseline number.
