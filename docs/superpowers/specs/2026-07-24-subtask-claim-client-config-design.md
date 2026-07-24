# Subtask Claim, Client Config Merge & Quick-Form Semantics — Design

**Date:** 2026-07-24  
**Status:** Approved design (brainstorming)  
**Extends:** `docs/superpowers/specs/2026-07-16-taskconfig-layout-design.md` (mostly implemented)  
**Scope:** Client config defaults + TaskConfig overrides; quick-form annotation uniqueness; browser overlay image-links default; subtask claim/filter API + UI; auto-claim on first write

## Context

The TaskConfig-driven viewer layout (quick-form / grading panel) is largely implemented and works. This design validates and tightens annotation semantics, introduces a proper client defaults → TaskConfig merge, and adds subtask assignment (claim) in the task viewer.

`SubTask.CreatorID` is already optional in the ORM. Listing filters by status exist; there is no claim path, no assignee filter, and `SubTaskGET` only exposes `creator_id` (no name). Browser overlay “Update task image links” defaults to unchecked with no TaskConfig override.

## Goals

- Quick-form: one FormAnnotation per **SubTask + FormSchema + Creator**; entity attachment from **FormSchema.EntityType** only.
- Remove TaskConfig `form_entity_scope` / `form_image_scope` overrides.
- Central **client config defaults**; TaskConfig is a same-shaped deep-merge override.
- Per-task override so grading tasks default “Update task image links” to checked.
- Claim unassigned subtasks (single + current page); filter All / Unassigned / Mine / pick assignee.
- Auto-claim on first relevant write when `CreatorID` is null (no steal).

## Non-goals

- Reassign, unclaim, or admin steal.
- Cross-page or whole-task batch claim.
- Claim UI inside the viewer (list page + auto-claim on write suffice).
- DB unique constraint on (SubTask, FormSchema, Creator) for FormAnnotation.
- Tags referencing subtasks (no `SubTaskID` on tags today).
- Auto-claim on annotation updates or add/remove subtask images.

---

## 1. Quick-form annotation + FormSchema scope

### Lookup (task / subtask context)

Match where:

- `form_schema_id` = schema from `form_schema_name`
- `creator.id` = current user
- `sub_task_id` = current subtask

Do **not** filter by patient/study/image/laterality for matching. If multiple rows match, use the **lowest `id`**. Never create a second annotation for that triple.

### Create

Only when lookup finds none. Set patient/study/image/laterality from **`FormSchema.EntityType`** and the current viewer image context (`buildFormAnnotationCreatePayload`).

### TaskConfig cleanup

- Remove `form_entity_scope` and deprecated `form_image_scope` from types, docs, and helpers.
- Scope resolution: `schema.entity_type`, else fallback `ImageInstance` if missing.
- Standard Form panel uses the same schema-only scope rule.

---

## 2. Client config + TaskConfig merge

### Shape

Overridable viewer/task settings live in one client config type. Defaults in `client/src/lib/config/` (e.g. `clientDefaults.ts`). Sibling modules (e.g. `builtinFormSchemas.ts`) stay for non-overridable constants.

```ts
export type ClientConfig = {
  form_schema_name?: string;
  update_subtask_image_links: boolean;
  layout: {
    hide: string[];
    prepend: Array<{
      type: "quick-form";
      title: string;
      expanded?: boolean;
    }>;
  };
};

export const CLIENT_DEFAULTS: ClientConfig = {
  update_subtask_image_links: false,
  layout: { hide: [], prepend: [] },
};
```

### Resolution

```ts
resolved = mergeClientConfig(CLIENT_DEFAULTS, taskDefinition?.config)
```

Merge rules:

- Scalars / missing keys: TaskConfig overrides when the key is present.
- `layout.hide` / `layout.prepend`: if TaskConfig provides the array, **replace** the default array (do not concatenate).
- Unknown TaskConfig keys: ignored by the merge helper (forward-compatible JSON).

Consumers:

- Browser overlay checkbox ← `resolved.update_subtask_image_links` (user may still toggle for that session).
- `resolvePanels` ← `resolved.layout` (empty hide/prepend = default builtin panel list).
- Quick-form schema ← `resolved.form_schema_name`.

**Rule:** new client constants / layout choices are added to `CLIENT_DEFAULTS` first; TaskConfig may override the same keys. Avoid one-off hardcoded defaults in components.

### Example grading TaskConfig (overrides only)

```json
{
  "form_schema_name": "Naevi grading",
  "update_subtask_image_links": true,
  "layout": {
    "hide": ["Form"],
    "prepend": [
      { "type": "quick-form", "title": "Grading", "expanded": true }
    ]
  }
}
```

Non-task browser mode: no checkbox; claim UI N/A.

---

## 3. Subtask claiming — API

### DTO

- Expose `creator: CreatorMeta | null` on `SubTaskGET` / `SubTaskWithImagesGET` (aligned with Task). Keep `creator_id` for backward compatibility (same id as `creator.id` when set). UI displays `creator`.

### PATCH `/subtasks/{id}`

Extend `SubTaskPATCH` with optional `claim: true`:

- If `claim: true` and `CreatorID` is null → set to current user.
- If `claim: true` and already set → **409 Conflict**; never overwrite.
- Do **not** accept arbitrary `creator_id` in the body.
- Existing `comments` / `task_state` remain; may be combined with `claim` in one request.

### List `GET /task/{task_id}/subtasks`

Add assignee filter (AND with existing `subtask_status`):

| Query | Meaning |
|-------|---------|
| (omitted) | All |
| `unassigned=true` | `CreatorID IS NULL` |
| `creator_id=<id>` | That creator |

`unassigned` and `creator_id` are mutually exclusive; sending both → **400**. Pagination unchanged.

### Assignees picker

`GET /task/{task_id}/subtask-assignees` → `CreatorMeta[]` for distinct non-null creators on that task’s subtasks. “Mine” is client-side (current user id).

### Batch claim

No batch route. Client loops unassigned IDs on the **current page** with `{ claim: true }`.

---

## 4. Task viewer UI

On `/tasks/[taskid]`:

- **Assignee column:** `creator.name` or “Unassigned”; **Claim** only when unassigned.
- **Claim all unassigned on this page** above the table.
- **Assignee filter** beside status: All / Unassigned / Mine / dropdown from subtask-assignees.
- Filters reset to page 0; sync to URL (`status`, `unassigned` / `creator_id`, `page`, `limit`).
- After claim: ingest updated subtasks (or reload page once for batch).

---

## 5. Auto-claim on first write

When a write references an unclaimed subtask, set `CreatorID` to the acting creator **only if null**.

### Triggers

- Create **FormAnnotation** with `SubTaskID` set
- Create **Segmentation** with `SubTaskID` set
- **PATCH subtask** that changes comments and/or `task_state` (even without `claim: true`)

### Does not trigger

- Add/remove subtask images
- Updates to existing FormAnnotation / Segmentation
- Tags (no `SubTaskID`)

### Implementation

`SubTaskRepository.claim_if_unassigned(session, subtask_id, creator_id) -> bool`  
Call from:

- `FormAnnotationService.create` (when `sub_task_id` present)
- `SegmentationService.create` (when `subtask_id` present)
- `SubTaskService.update_subtask` (on comments/state/claim updates)

Same DB session/transaction as the primary write. Importers that bypass these services should call the same helper or document the gap.

**UI note:** Grade on an unclaimed subtask creates a FormAnnotation → auto-claims. Explicit Claim remains for assigning without creating work yet.

---

## 6. Errors and edge cases

| Case | Behavior |
|------|----------|
| Explicit claim when already assigned | 409; UI does not offer Claim; batch skips / reports failures |
| Concurrent claim race | Second writer 409; first wins |
| Claim + comments/state in one PATCH | Allowed; still no overwrite of CreatorID |
| No unassigned on page | Batch disabled or no-op toast |
| Assignees list empty | All / Unassigned / Mine only |
| Multiple FormAnnotations for same triple | Show lowest `id`; do not create |
| TaskConfig omits `update_subtask_image_links` | `CLIENT_DEFAULTS` (`false`) |
| Auto-claim when already assigned | No-op (leave assignee) |

---

## 7. Testing

**Server**

- Claim null → self; claim when set → 409
- List filter unassigned / by `creator_id`
- Assignees endpoint
- SubTask DTO includes `creator`
- Auto-claim on FormAnnotation create, Segmentation create, comments PATCH; no steal; images add/remove does not claim

**Client**

- `mergeClientConfig(CLIENT_DEFAULTS, taskConfig)` (array replace for layout)
- `findFormAnnotation` by SubTask + Schema + Creator only
- Image-links checkbox initial value from resolved config

**Manual**

- Grading task: overlay checkbox checked by default
- Claim row + page batch
- Filter Mine / Unassigned / named assignee
- Grade on unclaimed subtask → assignee becomes current user

---

## Files (expected)

| Area | Likely touch |
|------|----------------|
| `client/src/lib/config/clientDefaults.ts` | **New** — defaults + types + merge helper |
| `client/src/lib/viewer-window/taskConfigLayout.ts` | Align with ClientConfig; drop scope overrides |
| `client/src/lib/viewer-window/panelForm/*` | Schema-only scope; find by triple |
| `client/src/lib/viewer-window/BrowserOverlay.svelte` | Resolved checkbox default |
| `client/src/routes/tasks/[taskid]/+page.svelte` | Filters, batch claim |
| `client/src/lib/tasks/SubTaskRow.svelte` / `SubtasksTable.svelte` | Assignee column, Claim |
| `server/routes/subtask.py` / `task.py` | claim PATCH; list filters; assignees |
| `server/services/*` / `orm/.../task_repository.py` | claim_if_unassigned + call sites |
| `server/dtos/dtos_tasks.py` / converter | `creator` on SubTask |
| Docs (`form_schemas.mdx`, tasks) | Config merge; drop scope overrides; claim |

---

## Future extensions (out of scope)

- Unclaim / reassign with permissions
- DB uniqueness for FormAnnotation (SubTask, Schema, Creator)
- Tag → SubTask linkage + auto-claim
- Whole-task claim-all
