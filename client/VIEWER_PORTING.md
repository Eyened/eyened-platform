# Viewer S2 port — working notes

Committed in sub-project 1 of the viewer S2 stack; deleted when the stack merges into `development`.

## Principles and standards

1. Show what the moment needs. 2. Eyes stay on the image. 3. Safe to try.
   IHE BIR (deviations in `DESIGN.md`) and WCAG 2.2 AA. Carbon owns the look and the feedback; the structure is ours, with S2, NN/g and TradingView cited as prior art.

## Checklist: ledger rows per sub-project

The ledger is the local spec `2026-11-02-viewer-workspace-ledger.md`. Rows are named here, not copied.

| Sub-project            | Rows                                                                                                                                      |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 0 (overview)           | V-015, V-042, V-046, V-048–V-054, V-165, V-171–V-173, N-3                                                                                 |
| 1 (frame and grid)     | V-004, V-017, V-019, V-020, V-026, V-033, V-034, V-035, V-036, V-037, V-038, V-041, V-043, V-044, V-047, V-151, V-175, V-176, N-2         |
| 2a (view controls)     | V-001–V-003, V-005–V-008, V-010–V-014, V-016, V-021, V-023, V-024, V-027                                                                  |
| 2b (linking)           | V-045; amends V-043, V-048–V-050                                                                                                          |
| 3 (tools)              | V-009, V-018, V-022, V-025, V-058, V-060, V-068–V-082, V-084, V-086, V-087, V-091, V-092, V-097, V-098, V-124, V-142, V-144, V-145, V-166 |
| 4 (layers)             | V-028, V-030–V-032, V-055, V-056, V-059, V-062–V-067, V-083, V-085, V-088, V-089, V-090, V-093–V-096, V-099–V-123, V-167                  |
| 5 (grading)            | V-125–V-127, V-129–V-141, V-143, V-146–V-156                                                                                              |
| 6 (images, info, help) | V-029, V-035, V-036, V-040, V-157–V-163, V-168–V-170, N-1                                                                                 |

## Old components not mounted

| Component                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Ported by                                                                                                        |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Per-viewport panels (`panelSegmentation` (except `PanelSegmentation.svelte`, deleted in 4a; its rows and parts now mount under Layers › Segmentations; 4b restyled the row details and replaced its two pickers with modals), `panelETRDS` (except `PanelETDRS.svelte`, deleted in 4c; its rows mount under Layers › ETDRS grids), `panelMeasure` (except `PanelMeasure.svelte` and its three area parts, deleted in 4c; `Line` mounts under Layers › Distance lines), `panelForm` (except `FormDeleteModal`, `FormItem`, `FormItemContent`, `formEntityScope` and `openForm`, which Grading and Forms use; `panelQuickForm`, `panelInfo`, `panelVisits` and `resolvePanels.ts` are deleted) and `panelRegistration`) | 3, 4, 5 and 6, per their ledger rows                                                                             |
| `HelpOverlay.svelte`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | 6 (Help panel)                                                                                                   |
| Task config `task_panel.enabled` / `task_panel.sections.*` and `layout.hide`: honoured since 5b by the header and Grading (sections) and by Layers and the tool rail (`layout.hide`, which now names Layers sections). `layout.prepend` and `task_panel.expanded` are removed and ignored.                                                                                                                                                                                                                                                                                                                                                                                                                            | 5                                                                                                                |
| `TopViewer.svelte`'s tile controls, dropped when it became `StripViewer.svelte`: copy-ID bar, localizer lines toggle, en-face projection cycling                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | 4d (V-028, V-030, V-167): copy-ID bar on the tile; localizer lines and projection in viewports, chosen in Layers |
| `RegistrationEditor` and `SeriesBlendEditor` overlays with their blend controls; `panelRendering/RenderModeSelect.svelte`, `panelRendering/WindowLevelSlider.svelte`, `DoubleRangeSlider.svelte` and `icons/Brightness.svelte`, kept only for those controls                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 4e: removed, not ported; Layers › Pointsets and Blend replace them; the four old controls are deleted            |

## Freeze rule

While the stack is open, a fix to the old viewer on `development` is listed here as a carry-over, with its commit, and ported into the sub-project that owns the behaviour.

| Commit            | Fix                                  | Ported in                        |
| ----------------- | ------------------------------------ | -------------------------------- |
| `80faf9bb` (#273) | Registration editor and series blend | 4e (engine kept, views replaced) |

## Traps

- The pick-up overlay of a splitter covers the grid, not the page, so no viewport takes the pointer while it is picked up. Pressing it keeps focus on the splitter (it prevents the mousedown default); a click outside the grid blurs the splitter and cancels.
- A press made while a popover, dropdown list or ⋯ list is open only closes it: `Viewer.svelte` drops it. A new floating component must carry one of the `data-slot` values that `Viewer.svelte` checks.
