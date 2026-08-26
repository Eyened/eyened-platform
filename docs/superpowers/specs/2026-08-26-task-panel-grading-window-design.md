# Task panel in the grading window — Design

**Date:** 2026-08-26  
**Status:** Approved  
**Branch:** `feat/205-task-status-grading-window`  
**Issue:** [#205](https://github.com/Eyened/eyened-platform/issues/205)  
**Scope:** Frontend — `client/` (SvelteKit 5). No API or ORM schema changes.

## Context

The grading window (`/tasks/[taskid]/grade/[setid]`) currently hides task status, prev/next, comments, and the task-overview link behind a full-screen overlay. The grader opens it from a task icon in `TopRowImages`. Viewing and changing subtask status is a frequent action; the overlay makes it slow.

That UI used to live in a top bar (`TaskTopBar`), then became `TaskOverlay`. Prev/next chevrons already sit in the top-row icon column, duplicated with the overlay’s own nav buttons.

`TaskDefinition.TaskConfig` is a free-form JSON blob. Today this branch only uses `form_schema_name` and `form_image_scope`. A parallel branch (`feat/dynamic-layout-from-taskconfig`) adds a `layout` object for MainViewer side panels. This work nests its knobs under `task_panel` so the two can coexist.

## Goals

- Show task navigation and status in a dedicated column on the right of the top-row thumbnails, not in a modal.
- Collapsed chrome still exposes compact title, prev/next, and status.
- Expanded chrome adds comments and “Task overview”.
- Sections and the default expanded/collapsed state are configurable via `TaskConfig.task_panel`.
- The grader’s expand/collapse choice persists in `localStorage` per task.
- Remove the task overlay and the duplicate prev/next/task icons. Help (`?`) and add-images (`+`) stay.

## Non-goals

- Jump-to-subtask list or progress counts by state.
- Full-height ViewerWindow rail or a MainViewer sidebar “Task” panel.
- Depending on or merging `feat/dynamic-layout-from-taskconfig`.
- Changing prev/next to client-side routing (full navigation stays as `TaskNavigation` does today).
- Keyboard shortcuts for status or expand/collapse.
- Backend validation of `TaskConfig` shape.

---

## Architecture

The grading window grid is unchanged (top row, resizer, main viewers). Task chrome moves into a column inside `TopRowImages`:

```
TopRowImages
  [ thumbnails … ]  [ TaskPanel ]  [ ?  + ]
```

`TopRowImages` mounts `TaskPanel` whenever `taskContext` exists. `TaskPanel` itself renders nothing if `task_panel.enabled` is false, so the top row does not parse config. Help and add-images stay in the existing icon strip. The overlay host keeps Help and Browser only; Escape still closes those.

Collapsed vs expanded is a **width change of that same column**, not a second surface.

| State | Width | Shows (if the section is enabled) |
|---|---|---|
| Collapsed | narrow; controls stacked vertically | title (`Set N of M`), prev/next, status |
| Expanded | wider | those plus comments and Task overview |

Expand/collapse is a control on the panel. Hide it when both `comments` and `overview` are off (nothing extra to reveal).

Status buttons remain `NotStarted` / `Busy` / `Ready` (`subTaskStates`). They stack in the column so the collapsed strip can stay narrow. Selection always follows the store after ingest. Use `aria-pressed={isActive}` on each status button (the overlay currently sets `aria-current="isActive"` as a literal string; do not copy that).

---

## Components

### `taskPanelConfig.ts` (`client/src/lib/tasks/`)

Parse `task.task_definition.config.task_panel`.

```ts
type TaskPanelSections = {
    title: boolean;
    nav: boolean;
    status: boolean;
    comments: boolean;
    overview: boolean;
};

type TaskPanelConfig = {
    enabled: boolean;
    expanded: boolean;
    sections: TaskPanelSections;
};
```

Defaults when `task_panel` is missing or partial:

- `enabled`: `true`
- `expanded`: `false` (collapsed)
- every section: `true`

Unknown keys are ignored. Wrong types fall back to those defaults (e.g. `expanded: "yes"` → `false`). `enabled: false` hides the whole column even on the grade route.

`TaskPanel` reads **`taskContext.task.task_definition.config`**, not `globalContext.config`, so these flags stay independent of unrelated keys (`form_schema_name`, annotation visibility, later `layout`).

Example `TaskConfig`:

```json
{
  "form_schema_name": "Naevi grading",
  "task_panel": {
    "expanded": true,
    "sections": { "comments": false }
  }
}
```

### `taskPanelExpandedPrefs.ts` (`client/src/lib/tasks/`)

`localStorage` key `eyened:taskPanelExpanded`, value `{ [taskId: string]: boolean }`. Same fail-soft pattern as `client/src/lib/viewer/imageUiPrefs.ts`.

- Stored value wins over config `expanded`.
- If none stored, use config `expanded`.
- Keyed by **task id**, not subtask id, so the choice survives prev/next (which currently does a full navigation).

### `TaskPanel.svelte` (`client/src/lib/tasks/`)

Refactor of `TaskOverlay.svelte`. Same actions: `TaskNavigation`, `updateSubTask`, `updateSubTaskComments`, overview link to `/tasks/{id}`. It is a column, not a modal. Dark styling to match the viewer chrome (not the overlay’s centered card on a blurred fullscreen).

`TaskOverlay.svelte` is deleted once `TaskPanel` is wired.

### `TopRowImages.svelte`

Between the thumbnail row and the icon strip:

- If `taskContext` exists → mount `TaskPanel` (the panel hides itself when `enabled` is false).
- Drop prev/next and the task icon.
- Overlay host: Help and Browser only.

No new `PanelName`, no MainViewer sidebar entry.

---

## Data flow

1. `TaskMain` already sets `taskContext` and calls `globalContext.updateConfig(task.task_definition.config)`. That merge is unchanged and unused by the panel.
2. `TaskPanel` parses `taskContext.task.task_definition.config.task_panel` through `taskPanelConfig`.
3. If `enabled` is false, render nothing.
4. Expanded UI state = `localStorage[taskId]` if present, else config `expanded`.
5. Each section renders only when its flag is true.
6. Status and comments go through existing `updateSubTask` / `updateSubTaskComments`. Those ingest into stores; the grade page derives `task` / `subTask` from stores, so the panel updates without a reload.

---

## Error handling

- Malformed `task_panel` never breaks the grade view: ignore unknown keys, coerce bad types to defaults.
- `localStorage` missing, quota errors, and bad JSON: fail soft. Read failure → config default. Write failure → toggle still works for this page load, does not survive prev/next.
- Status buttons disable while the patch is in flight (`aria-busy`). Comment save failures toast (existing). Status save failures toast too (the overlay currently swallows them). A failed status change must not leave a button looking selected.

---

## Testing

Vitest + Testing Library, same as `SortHeader.test.ts` and other client unit tests. No Playwright.

| File | Covers |
|---|---|
| `taskPanelConfig.test.ts` | Missing `task_panel`, partial `sections`, `enabled: false`, unknown keys, wrong types |
| `taskPanelExpandedPrefs.test.ts` | Get/set by task id, isolation between tasks, malformed JSON and `localStorage` throws |
| `TaskPanel.test.ts` | Collapsed vs expanded chrome; section flags hide widgets; `enabled: false` renders nothing; expand control hidden when comments and overview are both off; status click → `updateSubTask`; comment change → `updateSubTaskComments` (APIs mocked) |

`enabled: false` is asserted on `TaskPanel` (renders nothing). Do not add MainViewer panel tests.

---

## Docs

Add `task_panel` to the TaskConfig tables in:

- `docs/src/content/docs/orm/form_schemas.mdx` (TaskConfig for grading tasks)
- `docs/src/content/docs/orm/data_model/tasks.mdx` (short pointer)

No OpenAPI change; `TaskConfig` remains untyped JSON on the wire.
