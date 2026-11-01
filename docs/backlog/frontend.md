# Frontend

ESLint ratchet: after fixing a suppressed violation run `cd client && npx eslint . --prune-suppressions` and commit `eslint-suppressions.json`; never hand-merge that file. Run svelte-check in the dev container (`docker exec -w /app/client <client container> npx svelte-check --tsconfig ./tsconfig.json --output machine`); as your own user `.svelte-kit` EACCES errors inflate the counts.

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

### Hide the editing tools a project role does not allow
- **Status:** open
- **Source:** PR #247 review (bjliefers), 2026-10-01
- **Problem:** a `read_only` member still sees the FormAnnotation and segmentation tools; writes are refused with 403 only after the user has worked. The client cannot gate them: no response carries the caller's role per project (`UserResponse.role` is the legacy `Creator.Role`).
- **Fix:** expose the caller's effective role per project (e.g. a `{project_id: role}` map plus `is_admin` on `GET /auth/me`, or a `can_annotate` flag on the image/task DTOs) and gate the tool panels on it.
- **Note:** a task spanning projects needs the floor role in every one, so the gate must evaluate all projects the image or task touches.

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

### Remove small dead code
- **Status:** open
- **Source:** Phase 3 sweep
- **Problem:** `client/src/lib/viewer-window/icons/AV-Nicking.svelte` declares an inert `stroke` prop and has 0 callers.
- **Fix:** delete the component (or the prop).

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

### One date format across the client
- **Status:** open
- **Source:** client Carbon PR 4 (`ui/carbon-4-browser-search`) review, 2026-10-13
- **Problem:** the date picker types and shows ISO yyyy-mm-dd (P4 spec decision D8: the stored format, unambiguous in Dutch and English). A dd-mm-yyyy input was requested as more intuitive, but the client already shows dates in mixed formats: ISO in `browser/StudyBlock.svelte` (study header), `viewer-window/panelVisits/PanelVisits.svelte` and the `browser/dataSources.ts` results; "3 Oct 2026" in `lib/utils.ts` (en-GB); "Oct 3, 2026" in `viewer-window/panelForm/FormItem.svelte` (en-US); the browser locale in `viewer-window/panelForm/FormItemContent.svelte`.
- **Fix:** pick one display/input format: fixed dd-mm-yyyy, `Intl` locale-based, or unambiguous "13 Oct 2026" with lenient input. Amend D8 first. Keep ISO on the wire and in URLs; change only display and input. Show the format as visible helper text (Carbon date picker guidance), not only as a placeholder.
- **Note:** about 5-8 files, plus the tests `StudyBlock.test.ts`, `PanelVisits.test.ts` and `patientStudies.test.ts`.

### Round-trip a comma inside an "is one of" value
- **Status:** open
- **Source:** P4 browser search final review / demo 2026-10-13
- **Problem:** the value parser in `client/src/lib/browser/conditionConfig.ts` splits "is one of" text on commas and `condition-row.svelte` joins list values with ", ", so `["a,b"]` comes back as `["a","b"]`. Inherited v1 encoding.
- **Fix:** an escape or quoting rule for commas in the text, or a multi-value input instead of comma-separated text.

### Show portalled menus above the viewer overlay panel
- **Status:** open
- **Source:** client Carbon PR 4 demo, 2026-10-13
- **Problem:** in the viewer overlay, condition-builder popovers (and other portalled menus, such as the picker's menus noted in PR 3) render behind `div#panel` (`position: fixed; z-index: 1000` in `client/src/lib/viewer-window/TopRowImages.svelte:121-123`), because portal content uses `z-50` (`client/src/lib/components/ui/popover/popover-content.svelte:24`). Pointer clicks can't reach them; the keyboard still works. It predates the filter-column change.
- **Fix:** one shared layer order for overlays and portalled menus.

### Add a scroll-to-top button to the browser results
- **Status:** open
- **Source:** client Carbon PR 4 slide-over filter change, 2026-10-26
- **Problem:** the toolbar with the Filters button is not sticky and the filter column scrolls with the results (`client/src/lib/browser/Browser.svelte`), so far down a long result list the user scrolls all the way back up to change filters.
- **Fix:** a sticky bottom-right button that scrolls the results' scroll container (`Main.svelte` on `/`, the modal body in the picker) to the top; place it above the fixed `Selection` bar when images are selected.

### Open the image picker in a new tab
- **Status:** open
- **Source:** client Carbon PR 4 slide-over filter change, 2026-10-26
- **Problem:** the picker (`client/src/lib/browser/BrowserPicker.svelte`) puts the whole browser in a Modal lg: a second scroll container, a top `Selection` bar, and the form-in-form `stopPropagation` and Escape workarounds in `Browser.svelte`.
- **Fix:** "Browse images" in `SubTaskRow.svelte` opens `/` in a new tab with the subtask id and the patient condition; that tab pre-selects the set's images, saves with `addSubTaskImage`/`removeSubTaskImage` (move `confirmImages` to a shared module) and tells the task tab to refresh via `BroadcastChannel`. Then delete `BrowserPicker` and the Browser's `mode="overlay"` branch.
- **Note:** save in the new tab, not the opener: the task tab may have been reloaded or closed, and the error must show where the user is.

### Guard logged-in pages with a route group
- **Status:** open
- **Source:** signup-redirect fix on the Carbon branch, 2026-10-26
- **Problem:** which pages need a login is decided by path strings (`isPublicPath` in `client/src/lib/publicPaths.ts`) plus a separate redirect in `client/src/lib/components/Main.svelte`; a new public page must be added to the list or it bounces to login.
- **Fix:** move login, signup and oidc-callback under `routes/(public)/` and the rest under `routes/(app)/`, whose `+layout.ts` `load` checks the session and calls `redirect()`; then delete `publicPaths.ts` and the `Main.svelte` redirect.

### Cycle viewer regions with F6
- **Status:** open
- **Source:** viewer skin-mapping brainstorm, 2026-10-29
- **Problem:** to get from the form panel to the canvas, a keyboard user tabs back through about 20 tool and option controls; the viewer regions get landmarks but no shortcut between them.
- **Fix:** F6 / Shift+F6 on the viewer root move focus to the next/previous region (header, tool rail, options bar, canvas, right panel, timeline), each region restoring its last-focused element and hidden regions skipped (S2 `foundations/app-frame/creating-bluelines-browsing-context.md`, "Support F6 key navigation").
- **Note:** it needs an ADR 0006 deviation (viewer shortcuts work only while the image has focus), and a check that Chrome and Firefox let the page `preventDefault` F6.

### Create a feature from the viewer's segmentation panel
- **Status:** open
- **Source:** client Carbon PR 8 (`ui/carbon-8-library-leftovers`) brainstorm, 2026-10-30
- **Problem:** features can only be created on `/library`. The viewer's segmentation panel picks from the features loaded once at startup, so a grader who needs a new one leaves the viewer and reloads it.
- **Fix:** an inline `Create "<text>"` option in the panel's feature picker, as `AddTag` does for tags, adding the new feature to the loaded list.

### Let favourites sort the Tagger, or drop stars from the API
- **Status:** open
- **Source:** client Carbon PR 8 (`ui/carbon-8-library-leftovers`) brainstorm, 2026-10-30
- **Problem:** PR 8 removed the star buttons, which changed nothing visible. `starTag`/`unstarTag` in `client/src/lib/data/api.ts` and `userManager.starredTagIds` are now unused by the UI.
- **Fix:** either list starred tags first in the Tagger and bring the star back, or delete the star endpoints and client calls.

### Add column names to external data sources
- **Status:** open
- **Source:** client Carbon PR 8 (`ui/carbon-8-library-leftovers`) brainstorm, 2026-11-01
- **Problem:** `client/src/lib/utils/DataTable.svelte` shows no column headers because the source sends none, so screen readers cannot announce column names (a DESIGN.md deviation).
- **Fix:** an optional `columns` field in the data-source config, rendered as the table's header row when present.

### Show the filter count and Clear filters on the Library type filter
- **Status:** open
- **Source:** client Carbon PR 8 (`ui/carbon-8-library-leftovers`) Task 12a review, 2026-11-01
- **Problem:** below `md`, `/library`'s Tags Type filter sits behind an icon-only Filter button that shows neither the number of filters applied nor a way to clear them; Carbon Filtering, Filter states asks for both on the closed filter.
- **Fix:** the task page's pattern (`routes/tasks/[taskid]/+page.svelte`): a ghost lg `Filters (n)` button and a Clear filters button beside it.
