# Viewer S2 port — working notes

Committed in sub-project 1 of the viewer S2 stack; deleted when the stack merges into `development`.

## Principles and standards

1. Show what the moment needs. 2. Eyes stay on the image. 3. Safe to try.
   IHE BIR (deviations in `DESIGN.md`) and WCAG 2.2 AA. Carbon owns the look and the feedback; Spectrum 2 contributes structure patterns only.

## Checklist: ledger rows per sub-project

The ledger is the local spec `2026-11-02-viewer-workspace-ledger.md`. Rows are named here, not copied.

| Sub-project            | Rows                                                                                                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0 (overview)           | V-015, V-042, V-046, V-048–V-054, V-165, V-171–V-173, N-3                                                                                              |
| 1 (frame and grid)     | V-004, V-017, V-019, V-020, V-026, V-033, V-034, V-035, V-036, V-037, V-038, V-041, V-043, V-044, V-047, V-151, V-175, V-176, N-2                      |
| 2a (view controls)     | V-001–V-003, V-005–V-008, V-010–V-014, V-016, V-021, V-023, V-024, V-027                                                                               |
| 2b (linking)           | V-028, V-045; amends V-043, V-048–V-050                                                                                                                |
| 3 (tools)              | V-009, V-018, V-022, V-025, V-057, V-058, V-060, V-061, V-068–V-082, V-084, V-086–V-088, V-091, V-092, V-097, V-098, V-124, V-142, V-144, V-145, V-166 |
| 4 (layers)             | V-030–V-032, V-055, V-056, V-059, V-062–V-067, V-083, V-085, V-089, V-090, V-093–V-096, V-099–V-123                                                    |
| 5 (grading)            | V-125–V-127, V-129–V-141, V-143, V-146–V-156                                                                                                           |
| 6 (images, info, help) | V-029, V-035, V-036, V-040, V-157–V-163, V-167–V-170, N-1                                                                                              |

## Old components not mounted

| Component                                                                                                                                                                                                                                                                                                                          | Ported by                                |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Per-viewport panels (`panelSegmentation`, `panelForm`, `panelQuickForm`, `panelMeasure`, `panelETRDS`, `panelRegistration`, `panelInfo`, `panelVisits`) and `resolvePanels.ts`                                                                                                                                                     | 3, 4, 5 and 6, per their ledger rows     |
| `tasks/TaskPanel.svelte` (status, comments)                                                                                                                                                                                                                                                                                        | 5                                        |
| `HelpOverlay.svelte`                                                                                                                                                                                                                                                                                                               | 6 (Help panel)                           |
| Task config `task_panel.enabled` / `task_panel.sections.*` and `layout.hide` / `layout.prepend`: not honoured while the old panels are unmounted, except `hide: ["Rendering"]`, which `MainViewer` honours (no bar, no mode keys), so a task that hides navigation still shows Previous / Next set and Task overview in the header | 5                                        |
| `TopViewer.svelte`'s tile controls, dropped when it became `StripViewer.svelte`: copy-ID bar, localizer lines toggle, en-face projection cycling                                                                                                                                                                                   | 6 (V-167), 2b (V-028, ported), 4 (V-030) |
| `RegistrationEditor` and `SeriesBlendEditor` overlays with their blend controls; `panelRendering/RenderModeSelect.svelte`, `panelRendering/WindowLevelSlider.svelte`, `DoubleRangeSlider.svelte` and `icons/Brightness.svelte`, kept only for those controls                                                                       | 4d, which deletes the last four          |

## Freeze rule

While the stack is open, a fix to the old viewer on `development` is listed here as a carry-over, with its commit, and ported into the sub-project that owns the behaviour.

| Commit            | Fix                                  | Ported in |
| ----------------- | ------------------------------------ | --------- |
| `80faf9bb` (#273) | Registration editor and series blend | 4d        |

## Traps

- The pick-up overlay of a splitter covers the grid, not the page, so no viewport takes the pointer while it is picked up. Pressing it keeps focus on the splitter (it prevents the mousedown default); a click outside the grid blurs the splitter and cancels.
- A press that closes a bits-ui popover also reaches the image underneath, against overview §3 (a dismissing press only dismisses). No tool can be armed before sub-project 3, which must fix this for the view bar's popovers and the Layout popover.
