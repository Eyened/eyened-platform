# Subtask Claim, Client Config Merge & Quick-Form Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify client defaults with TaskConfig overrides, fix quick-form annotation uniqueness to SubTask+FormSchema+Creator with FormSchema-only entity scope, add subtask claim/filter UI+API, and auto-claim on first FormAnnotation/Segmentation create or subtask comments/state PATCH.

**Architecture:** `CLIENT_DEFAULTS` in `client/src/lib/config/` deep-merged with TaskDefinition JSON (arrays replace). Backend `SubTaskRepository.claim_if_unassigned` is the single no-steal assign helper; services call it on create/PATCH; explicit `claim: true` on SubTask PATCH raises `ConflictError` (409) if already assigned. Task list gains assignee filters + page batch claim via existing PATCH.

**Tech Stack:** SvelteKit 5 / TypeScript / Vitest (client); FastAPI / SQLAlchemy / pytest (server); `make gen-types` for OpenAPI client types.

## Global Constraints

Copied from `docs/superpowers/specs/2026-07-24-subtask-claim-client-config-design.md`. Every task implicitly includes these:

- **Branch:** `feat/dynamic-layout-from-taskconfig` (continue on this branch).
- **No steal:** never overwrite a non-null `SubTask.CreatorID`.
- **Claim batch:** current page unassigned only — no whole-task batch endpoint.
- **Entity scope:** from `FormSchema.EntityType` only — remove TaskConfig `form_entity_scope` / `form_image_scope`.
- **Quick-form lookup (when `subTaskId` set):** SubTask + FormSchema + Creator; lowest `id` if multiples; never create a second for that triple.
- **Auto-claim triggers only:** FormAnnotation create with SubTaskID; Segmentation create with SubTaskID; SubTask PATCH comments and/or task_state. Not image add/remove; not annotation updates; not tags.
- **Config rule:** new overridable knobs go in `CLIENT_DEFAULTS` first; TaskConfig overrides same keys; `layout.hide` / `layout.prepend` **replace** arrays when provided.
- **No mocking library** in Python tests; use real `session` fixture.
- **Interpreter:** `dev/.venv/bin/pytest` / `dev/.venv/bin/python`. Prefix server imports with `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password` when needed.
- **Client commands:** from `client/` — `npm test`, `npm run check`.

---

## File structure

| File | Responsibility |
|------|----------------|
| `client/src/lib/config/clientDefaults.ts` | `ClientConfig`, `CLIENT_DEFAULTS`, `mergeClientConfig` |
| `client/src/lib/config/clientDefaults.test.ts` | Merge unit tests |
| `client/src/lib/viewer-window/taskConfigLayout.ts` | Re-export / thin alias onto `ClientConfig` (drop scope fields) |
| `client/src/lib/viewer-window/panelForm/formEntityScope.ts` | Schema-only `resolveFormEntityScope` |
| `client/src/lib/viewer-window/panelForm/findFormAnnotation.ts` | Triple lookup when subTaskId set |
| `client/src/lib/viewer-window/BrowserOverlay.svelte` | Checkbox from resolved config |
| `orm/eyened_orm/repositories/task_repository.py` | `claim_if_unassigned`, list/count filters, assignees |
| `server/services/task_service.py` | claim PATCH, filters, auto-claim on update |
| `server/services/form_annotation_service.py` | auto-claim on create |
| `server/services/segmentation_service.py` | auto-claim on create |
| `server/routes/subtask.py` / `task.py` | claim body; list query; assignees route |
| `server/dtos/dtos_tasks.py` + `dto_converter.py` | `creator` on SubTask GET |
| `client/src/routes/tasks/[taskid]/+page.svelte` + task table components | Claim UI + filters |
| Docs under `docs/src/content/docs/` | Config merge; drop scope overrides; claim |

---

## Task 0: Baseline

- [ ] **Step 1: Confirm branch**

```bash
git branch --show-current
# expect: feat/dynamic-layout-from-taskconfig
```

- [ ] **Step 2: Client tests green**

Run: `cd client && npm test`  
Expected: PASS (existing suite).

- [ ] **Step 3: Server/orm tests green**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest server/tests/test_subtask_service.py orm/eyened_orm/tests/test_task_repository.py -q`  
Expected: PASS.

---

## Task 1: `CLIENT_DEFAULTS` + `mergeClientConfig`

**Files:**
- Create: `client/src/lib/config/clientDefaults.ts`
- Create: `client/src/lib/config/clientDefaults.test.ts`

**Interfaces:**
- Produces:
  - `ClientConfig` type (see spec)
  - `CLIENT_DEFAULTS: ClientConfig`
  - `mergeClientConfig(defaults: ClientConfig, override: unknown): ClientConfig`

- [ ] **Step 1: Write failing tests**

Create `client/src/lib/config/clientDefaults.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { CLIENT_DEFAULTS, mergeClientConfig } from "./clientDefaults";

describe("mergeClientConfig", () => {
    it("returns defaults when override is missing or not an object", () => {
        expect(mergeClientConfig(CLIENT_DEFAULTS, undefined)).toEqual(
            CLIENT_DEFAULTS,
        );
        expect(mergeClientConfig(CLIENT_DEFAULTS, null)).toEqual(
            CLIENT_DEFAULTS,
        );
    });

    it("overrides update_subtask_image_links", () => {
        const resolved = mergeClientConfig(CLIENT_DEFAULTS, {
            update_subtask_image_links: true,
        });
        expect(resolved.update_subtask_image_links).toBe(true);
        expect(resolved.layout).toEqual(CLIENT_DEFAULTS.layout);
    });

    it("replaces layout.hide and layout.prepend arrays (no concat)", () => {
        const resolved = mergeClientConfig(CLIENT_DEFAULTS, {
            layout: {
                hide: ["Form"],
                prepend: [
                    { type: "quick-form", title: "Grading", expanded: true },
                ],
            },
        });
        expect(resolved.layout.hide).toEqual(["Form"]);
        expect(resolved.layout.prepend).toEqual([
            { type: "quick-form", title: "Grading", expanded: true },
        ]);
    });

    it("ignores unknown keys", () => {
        const resolved = mergeClientConfig(CLIENT_DEFAULTS, {
            totally_unknown: 1,
            form_schema_name: "Naevi grading",
        });
        expect(resolved.form_schema_name).toBe("Naevi grading");
        expect(
            (resolved as Record<string, unknown>).totally_unknown,
        ).toBeUndefined();
    });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd client && npx vitest run src/lib/config/clientDefaults.test.ts`  
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

Create `client/src/lib/config/clientDefaults.ts`:

```typescript
export type QuickFormPanelConfig = {
    type: "quick-form";
    title: string;
    expanded?: boolean;
};

export type ClientConfigLayout = {
    hide: string[];
    prepend: QuickFormPanelConfig[];
};

export type ClientConfig = {
    form_schema_name?: string;
    update_subtask_image_links: boolean;
    layout: ClientConfigLayout;
};

export const CLIENT_DEFAULTS: ClientConfig = {
    update_subtask_image_links: false,
    layout: { hide: [], prepend: [] },
};

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isQuickFormPanel(value: unknown): value is QuickFormPanelConfig {
    if (!isRecord(value)) return false;
    return (
        value.type === "quick-form" &&
        typeof value.title === "string" &&
        (value.expanded === undefined || typeof value.expanded === "boolean")
    );
}

export function mergeClientConfig(
    defaults: ClientConfig,
    override: unknown,
): ClientConfig {
    if (!isRecord(override)) {
        return {
            ...defaults,
            layout: {
                hide: [...defaults.layout.hide],
                prepend: [...defaults.layout.prepend],
            },
        };
    }

    const next: ClientConfig = {
        ...defaults,
        layout: {
            hide: [...defaults.layout.hide],
            prepend: [...defaults.layout.prepend],
        },
    };

    if (typeof override.form_schema_name === "string") {
        next.form_schema_name = override.form_schema_name;
    }
    if (typeof override.update_subtask_image_links === "boolean") {
        next.update_subtask_image_links = override.update_subtask_image_links;
    }

    if (isRecord(override.layout)) {
        const layout = override.layout;
        if (Array.isArray(layout.hide)) {
            next.layout.hide = layout.hide.filter(
                (x): x is string => typeof x === "string",
            );
        }
        if (Array.isArray(layout.prepend)) {
            next.layout.prepend = layout.prepend.filter(isQuickFormPanel);
        }
    }

    return next;
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd client && npx vitest run src/lib/config/clientDefaults.test.ts`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/config/clientDefaults.ts client/src/lib/config/clientDefaults.test.ts
git commit -m "$(cat <<'EOF'
feat(client): add CLIENT_DEFAULTS and mergeClientConfig

Central overridable task/viewer settings with TaskConfig-shaped overrides
and replace semantics for layout arrays.
EOF
)"
```

---

## Task 2: Wire config merge; drop TaskConfig scope overrides

**Files:**
- Modify: `client/src/lib/viewer-window/taskConfigLayout.ts`
- Modify: `client/src/lib/viewer-window/resolvePanels.ts` (and tests if they pass raw TaskConfig)
- Modify: `client/src/lib/viewer-window/panelForm/formEntityScope.ts`
- Modify: `client/src/lib/viewer-window/panelForm/formEntityScope.test.ts`
- Modify: any imports of `form_entity_scope` / `form_image_scope` under `client/`

**Interfaces:**
- Consumes: `mergeClientConfig`, `CLIENT_DEFAULTS`, `ClientConfig`
- Produces: `resolveFormEntityScope(schemaEntityType)` — schema only (optional second arg removed or ignored)
- `TaskConfig` becomes alias / partial of `ClientConfig` without scope fields

- [ ] **Step 1: Update failing scope tests**

Replace `formEntityScope.test.ts` `resolveFormEntityScope` suite with:

```typescript
describe("resolveFormEntityScope", () => {
    it("uses schema entity type", () => {
        expect(resolveFormEntityScope("StudyEye")).toBe("StudyEye");
    });

    it("falls back to ImageInstance when schema type missing", () => {
        expect(resolveFormEntityScope(undefined)).toBe("ImageInstance");
        expect(resolveFormEntityScope(null)).toBe("ImageInstance");
    });
});
```

Remove tests that assert TaskConfig / `form_image_scope` overrides.

- [ ] **Step 2: Run — expect FAIL**

Run: `cd client && npx vitest run src/lib/viewer-window/panelForm/formEntityScope.test.ts`  
Expected: FAIL (signature / behavior mismatch).

- [ ] **Step 3: Implement schema-only resolve + taskConfigLayout cleanup**

`formEntityScope.ts` — change to:

```typescript
export function resolveFormEntityScope(
    schemaEntityType: FormSchemaGET["entity_type"] | null | undefined,
): FormEntityScope {
    return schemaEntityType ?? "ImageInstance";
}
```

Remove `TaskFormScopeConfig` if unused, or leave deprecated unused type deleted.

`taskConfigLayout.ts` — re-export from config:

```typescript
export type {
    ClientConfig as TaskConfig,
    ClientConfigLayout as TaskConfigLayout,
    QuickFormPanelConfig,
} from "$lib/config/clientDefaults";
export { CLIENT_DEFAULTS, mergeClientConfig } from "$lib/config/clientDefaults";
```

Update all call sites of `resolveFormEntityScope(taskConfig, schema.entity_type)` → `resolveFormEntityScope(schema.entity_type)`.

Where panels read `task.task_definition.config`, resolve via:

```typescript
const resolved = mergeClientConfig(
    CLIENT_DEFAULTS,
    taskContext?.task.task_definition.config,
);
```

Use `resolved.layout` in `resolvePanels` / MainViewer; use `resolved.form_schema_name` in PanelQuickForm / PanelForm.

- [ ] **Step 4: Run client tests**

Run: `cd client && npm test`  
Expected: PASS (update `resolvePanels.test.ts` / any TaskConfig fixtures that set `form_entity_scope`).

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window client/src/lib/config
git commit -m "$(cat <<'EOF'
refactor(client): merge TaskConfig over CLIENT_DEFAULTS; drop scope overrides

Entity attachment scope comes only from FormSchema.EntityType.
EOF
)"
```

---

## Task 3: Quick-form find = SubTask + Schema + Creator

**Files:**
- Modify: `client/src/lib/viewer-window/panelForm/findFormAnnotation.ts`
- Modify: `client/src/lib/viewer-window/panelForm/findFormAnnotation.test.ts`
- Modify: `client/src/lib/viewer-window/panelQuickForm/PanelQuickForm.svelte` (call sites)

**Interfaces:**
- `findFormAnnotation({ annotations, schemaId, userId, ctx, subTaskId?, schemaEntityType })`
  - When `subTaskId !== undefined`: match schemaId + userId + sub_task_id; **ignore** entity fields; return **lowest** `id`.
  - Else: match schemaId + userId + `matchesFormEntityScope(..., resolveFormEntityScope(schemaEntityType), ctx)`; return lowest `id`.

- [ ] **Step 1: Rewrite tests**

```typescript
import { describe, it, expect } from "vitest";
import { findFormAnnotation } from "./findFormAnnotation";
import type { FormAnnotationGET } from "../../../types/openapi_types";

const base = {
    form_schema_id: 10,
    patient_id: 100,
    creator: { id: 5, name: "grader" },
    form_data: {},
} as FormAnnotationGET;

const ctx = {
    patientId: 100,
    studyId: 50,
    imageId: "img-200",
    laterality: "R" as const,
};

describe("findFormAnnotation", () => {
    it("in subtask context matches schema+creator+subtask only (ignores image)", () => {
        const annotations = [
            {
                ...base,
                id: 2,
                sub_task_id: 7,
                image_id: "other",
            },
            {
                ...base,
                id: 1,
                sub_task_id: 7,
                image_id: "img-200",
            },
        ] as FormAnnotationGET[];

        const result = findFormAnnotation({
            annotations,
            schemaId: 10,
            userId: 5,
            ctx,
            subTaskId: 7,
            schemaEntityType: "ImageInstance",
        });

        expect(result?.id).toBe(1); // lowest id
    });

    it("in subtask context does not create-match wrong subtask", () => {
        const annotations = [
            { ...base, id: 1, sub_task_id: 99, image_id: "img-200" },
        ] as FormAnnotationGET[];

        expect(
            findFormAnnotation({
                annotations,
                schemaId: 10,
                userId: 5,
                ctx,
                subTaskId: 7,
                schemaEntityType: "ImageInstance",
            }),
        ).toBeUndefined();
    });

    it("without subtask uses schema entity scope", () => {
        const annotations = [
            { ...base, id: 3, image_id: "img-200" },
            { ...base, id: 4, image_id: "other" },
        ] as FormAnnotationGET[];

        expect(
            findFormAnnotation({
                annotations,
                schemaId: 10,
                userId: 5,
                ctx,
                schemaEntityType: "ImageInstance",
            })?.id,
        ).toBe(3);
    });
});
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd client && npx vitest run src/lib/viewer-window/panelForm/findFormAnnotation.test.ts`  
Expected: FAIL (still filters by entity / highest id).

- [ ] **Step 3: Implement**

```typescript
export function findFormAnnotation(
    params: FindFormAnnotationParams,
): FormAnnotationGET | undefined {
    const matches = params.annotations.filter((annotation) => {
        if (annotation.form_schema_id !== params.schemaId) return false;
        if (annotation.creator?.id !== params.userId) return false;

        if (params.subTaskId !== undefined) {
            return annotation.sub_task_id === params.subTaskId;
        }

        const scope = resolveFormEntityScope(params.schemaEntityType);
        return matchesFormEntityScope(annotation, scope, params.ctx);
    });

    if (!matches.length) return undefined;
    return matches.reduce((best, current) =>
        current.id < best.id ? current : best,
    );
}
```

Remove `taskConfig` from params and all call sites.

- [ ] **Step 4: Run client tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/panelForm client/src/lib/viewer-window/panelQuickForm
git commit -m "$(cat <<'EOF'
fix(viewer): find FormAnnotation by SubTask+Schema+Creator in tasks

Ignore entity fields when subTaskId is set; prefer lowest id if duplicates.
EOF
)"
```

---

## Task 4: Browser overlay checkbox from resolved config

**Files:**
- Modify: `client/src/lib/viewer-window/BrowserOverlay.svelte`

**Interfaces:**
- Consumes: `mergeClientConfig(CLIENT_DEFAULTS, taskContext?.task.task_definition.config).update_subtask_image_links`

- [ ] **Step 1: Initialize checkbox from resolved config**

Replace `let updateImageLinks = $state(false);` with:

```typescript
import {
    CLIENT_DEFAULTS,
    mergeClientConfig,
} from "$lib/config/clientDefaults";

const resolvedConfig = mergeClientConfig(
    CLIENT_DEFAULTS,
    taskContext?.task?.task_definition?.config,
);
let updateImageLinks = $state(resolvedConfig.update_subtask_image_links);
```

(Adjust property access to match existing `taskContext` shape — same as PanelQuickForm.)

- [ ] **Step 2: Manual check note** (no automated UI test required)

Grading TaskConfig with `"update_subtask_image_links": true` → checkbox checked on open.

- [ ] **Step 3: Commit**

```bash
git add client/src/lib/viewer-window/BrowserOverlay.svelte
git commit -m "$(cat <<'EOF'
feat(viewer): default Update task image links from merged client config
EOF
)"
```

---

## Task 5: `SubTaskRepository.claim_if_unassigned` + list filters + assignees

**Files:**
- Modify: `orm/eyened_orm/repositories/task_repository.py`
- Modify: `orm/eyened_orm/tests/test_task_repository.py`

**Interfaces:**
- `claim_if_unassigned(session, subtask_id: int, creator_id: int) -> bool`  
  — If subtask missing → treat as no-op return `False` (services already 404 separately) **or** return False when not found; callers that need existence check `get_by_id` first. Prefer: load subtask; if None return False; if `CreatorID is None` set to `creator_id`, return True; else return False. **Does not commit.**
- Extend `count_for_task` / `list_for_task` with `creator_id: int | None = None` and `unassigned: bool = False` (when `unassigned`, filter `CreatorID.is_(None)`; when `creator_id` set, filter equality). Caller must not pass both.
- `list_assignees_for_task(session, task_id: int) -> list[Creator]` — distinct non-null creators on that task’s subtasks, ordered by name.

Also eager-load `SubTask.Creator` on list/get paths used by DTO (add `selectinload(SubTask.Creator)` to list queries and `get_by_id` usage sites that convert to GET — or a `_SUBTASK_CREATOR_LOADER` option on list/get_with_images).

- [ ] **Step 1: Write repository tests**

Append to `orm/eyened_orm/tests/test_task_repository.py`:

```python
def test_claim_if_unassigned_sets_creator(session):
    """Unassigned subtask is claimed by the given creator_id."""
    actor = _creator(session, "claimer")
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    session.commit()

    claimed = SubTaskRepository().claim_if_unassigned(
        session, st.SubTaskID, actor.CreatorID
    )
    session.commit()

    assert claimed is True
    assert session.get(SubTask, st.SubTaskID).CreatorID == actor.CreatorID


def test_claim_if_unassigned_does_not_steal(session):
    """Already-assigned subtask is left unchanged."""
    owner = _creator(session, "owner")
    other = _creator(session, "other")
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.CreatorID)
    st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    st.CreatorID = owner.CreatorID
    session.commit()

    claimed = SubTaskRepository().claim_if_unassigned(
        session, st.SubTaskID, other.CreatorID
    )
    session.commit()

    assert claimed is False
    assert session.get(SubTask, st.SubTaskID).CreatorID == owner.CreatorID


def test_list_for_task_filters_unassigned_and_creator(session):
    """list_for_task honors unassigned=True and creator_id filters."""
    owner = _creator(session, "owner")
    other = _creator(session, "other")
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.CreatorID)
    unassigned = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    owned = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    owned.CreatorID = owner.CreatorID
    other_st = _make_subtask(session, task.TaskID, SubTaskState.NotStarted)
    other_st.CreatorID = other.CreatorID
    session.commit()

    repo = SubTaskRepository()
    only_unassigned = repo.list_for_task(
        session, task.TaskID, unassigned=True, limit=50, offset=0
    )
    assert [r.SubTaskID for r in only_unassigned] == [unassigned.SubTaskID]

    only_owner = repo.list_for_task(
        session,
        task.TaskID,
        creator_id=owner.CreatorID,
        limit=50,
        offset=0,
    )
    assert [r.SubTaskID for r in only_owner] == [owned.SubTaskID]
```

- [ ] **Step 2: Run — expect FAIL**

Run: `dev/.venv/bin/pytest orm/eyened_orm/tests/test_task_repository.py -k claim_if_unassigned -v`  
Expected: FAIL (method missing).

- [ ] **Step 3: Implement repository methods**

```python
def claim_if_unassigned(
    self, session: Session, subtask_id: int, creator_id: int
) -> bool:
    subtask = session.get(SubTask, subtask_id)
    if subtask is None:
        return False
    if subtask.CreatorID is not None:
        return False
    subtask.CreatorID = creator_id
    return True
```

Extend `list_for_task` / `count_for_task` filters; implement `list_assignees_for_task` with a distinct join on `Creator` where `SubTask.TaskID == task_id` and `CreatorID.is_not(None)`.

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/task_repository.py orm/eyened_orm/tests/test_task_repository.py
git commit -m "$(cat <<'EOF'
feat(orm): claim_if_unassigned and subtask assignee list filters
EOF
)"
```

---

## Task 6: Auto-claim in FormAnnotation + Segmentation + SubTask update

**Files:**
- Modify: `server/services/form_annotation_service.py`
- Modify: `server/services/segmentation_service.py`
- Modify: `server/services/task_service.py` (`SubTaskService.update_subtask`)
- Modify: `server/tests/test_form_annotation_service.py`
- Modify: `server/tests/test_subtask_service.py`
- Add or modify segmentation create tests if present

**Interfaces:**
- Inject `SubTaskRepository` into `FormAnnotationService` and `SegmentationService` (constructor + `get_*_service` wiring + test helpers).
- Before `session.commit()` on create when subtask id set: `self.subtasks.claim_if_unassigned(session, sub_task_id, actor.id)`.
- `update_subtask(..., claim: bool | None = None)`: on comments/state change and/or successful claim path, call `claim_if_unassigned` for auto-claim when not using explicit-claim-409 path (Task 7 wires 409).

For this task, implement auto-claim on comments/state update:

```python
if comments is not None or task_state is not None:
    self.subtasks.claim_if_unassigned(session, subtask_id, actor.id)
```

(Explicit `claim` parameter added in Task 7.)

- [ ] **Step 1: Failing service tests**

In `test_form_annotation_service.py`: create annotation with `sub_task_id` on unassigned subtask → after create, `SubTask.CreatorID == actor.id`.

Create on already-assigned subtask → CreatorID unchanged.

In `test_subtask_service.py`: `update_subtask` comments on unassigned → CreatorID set; on assigned → unchanged.

Segmentation: same pattern if create tests exist; otherwise add a focused test.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement wiring + calls before commit**

Ensure claim runs in the **same** session before `commit()`.

Update `_service()` test helpers to pass `SubTaskRepository()`.

- [ ] **Step 4: Run relevant pytest — PASS**

Run: `EYENED_DATABASE_USER=test_user EYENED_DATABASE_PASSWORD=test_password dev/.venv/bin/pytest server/tests/test_form_annotation_service.py server/tests/test_subtask_service.py -q`

- [ ] **Step 5: Commit**

```bash
git add server/services server/tests
git commit -m "$(cat <<'EOF'
feat(server): auto-claim subtask on annotation create and comments PATCH
EOF
)"
```

---

## Task 7: Explicit `claim: true` on SubTask PATCH (409 if taken)

**Files:**
- Modify: `server/routes/subtask.py` (`SubTaskPATCH`)
- Modify: `server/services/task_service.py`
- Modify: `server/tests/test_subtask_service.py`

**Interfaces:**
- `SubTaskPATCH.claim: Optional[bool] = None`
- `SubTaskService.update_subtask(..., claim: bool | None = None)`
- When `claim is True`:
  - If `subtask.CreatorID is not None` → raise `ConflictError({"code": "subtask_already_claimed", "message": "SubTask is already assigned", "creator_id": subtask.CreatorID})`
  - Else set via `claim_if_unassigned` (or direct assign)
- When `claim` is not True: existing auto-claim on comments/state only

- [ ] **Step 1: Tests**

```python
from server.services.exceptions import ConflictError


def test_update_subtask_claim_assigns(session):
    """claim=True on an unassigned subtask sets CreatorID to the actor."""
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, actor.id)
    st = _make_subtask(session, task.TaskID)
    session.commit()

    updated = _service().update_subtask(
        session, st.SubTaskID, None, None, actor, claim=True
    )
    assert updated.CreatorID == actor.id


def test_update_subtask_claim_conflict_when_assigned(session):
    """claim=True on an already-assigned subtask raises ConflictError."""
    owner = _actor(session)
    actor = _actor(session)
    td = _task_def(session)
    task = _make_task(session, td.TaskDefinitionID, owner.id)
    st = _make_subtask(session, task.TaskID)
    st.CreatorID = owner.id
    session.commit()

    with pytest.raises(ConflictError) as exc:
        _service().update_subtask(
            session, st.SubTaskID, None, None, actor, claim=True
        )
    assert exc.value.detail["code"] == "subtask_already_claimed"
```

Note: `_actor` creates a new Creator each call — use two calls for owner vs claimer as above.
- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement service + route**

Route (`server/routes/subtask.py`):

```python
st = service.update_subtask(
    db,
    subtaskid,
    dto.comments,
    dto.task_state,
    ActingUser(id=current_user.id, username=current_user.username),
    claim=dto.claim,
)
```
- [ ] **Step 4: PASS + commit**

```bash
git commit -m "$(cat <<'EOF'
feat(api): claim subtask via PATCH with 409 when already assigned
EOF
)"
```

---

## Task 8: List filters, assignees endpoint, SubTask `creator` DTO

**Files:**
- Modify: `server/dtos/dtos_tasks.py` — add `creator: Optional[CreatorMeta] = None` on `SubTaskGET`
- Modify: `server/dtos/dto_converter.py` — populate `creator` like Task
- Modify: `server/services/task_service.py` — pass filter args; `list_subtask_assignees`
- Modify: `server/routes/task.py` — query params + new route
- Modify: `server/tests/test_task_service.py`

**Interfaces:**
- `GET /task/{task_id}/subtasks?unassigned=true` XOR `?creator_id=N` — both → `BadRequestError("unassigned and creator_id are mutually exclusive")`
- `GET /task/{task_id}/subtask-assignees` → `list[CreatorMeta]` (response model: `List[CreatorMeta]` or small wrapper)

- [ ] **Step 1: Service/route tests for filters + assignees + DTO creator field**

- [ ] **Step 2: Implement**

Ensure list queries `selectinload(SubTask.Creator)` so converter can read `subtask.Creator`.

```python
creator=(
    DTOConverter.creator_to_meta(subtask.Creator)
    if getattr(subtask, "Creator", None)
    else None
),
creator_id=subtask.CreatorID,
```

- [ ] **Step 3: Regenerate OpenAPI client types**

```bash
make gen-types
```

Expected: `client/src/types/openapi.ts` / `openapi.json` include `claim` on SubTaskPATCH, `creator` on SubTaskGET, new assignees path, list query params.

- [ ] **Step 4: Commit**

```bash
git add server/ client/src/types/
git commit -m "$(cat <<'EOF'
feat(api): filter subtasks by assignee and expose creator on SubTaskGET
EOF
)"
```

---

## Task 9: Client API helpers + task page claim UI

**Files:**
- Modify: `client/src/lib/data/api.ts` — `updateSubTask` body `{ claim?: boolean }`; `fetchSubTasks` params `unassigned?`, `creator_id?`; add `fetchSubTaskAssignees(taskId)`
- Modify: `client/src/routes/tasks/[taskid]/+page.svelte`
- Modify: `client/src/lib/tasks/SubtasksTable.svelte`
- Modify: `client/src/lib/tasks/SubTaskRow.svelte`

**Interfaces:**
- Row: show assignee; Claim button → `updateSubTask(id, { claim: true })`; toast on 409
- Table toolbar / page: “Claim all unassigned on this page” loops unassigned rows
- Filter: All | Unassigned | Mine | `<select>` from assignees endpoint
- URL sync: `unassigned=1` or `creator_id=` alongside `status`/`page`/`limit`

- [ ] **Step 1: Extend `updateSubTask` / `fetchSubTasks`**

```typescript
export async function updateSubTask(
    subtask_id: number,
    patch: {
        task_state?: any;
        comments?: string | null;
        claim?: boolean;
    },
): Promise<any> {
    const data = await apiPatch<any>("/subtasks/{subtaskid}" as any, {
        params: { path: { subtaskid: Number(subtask_id) } } as any,
        body: patch as any,
    });
    ingestSubTasks([data]);
    return data;
}
```
- [ ] **Step 2: UI wiring on task page + row**

Assignee column between Status and View (or after Status). Batch button above table; disable when no unassigned on page.

Mine filter: `creator_id = globalContext.user.id` (get user the same way other pages do — `getContext("globalContext")` or existing store).

- [ ] **Step 3: Smoke `npm test` / `npm run check` for new errors only**

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(client): claim subtasks and filter by assignee on task page
EOF
)"
```

---

## Task 10: Documentation

**Files:**
- Modify: `docs/src/content/docs/orm/form_schemas.mdx` — remove `form_entity_scope` / `form_image_scope`; document `update_subtask_image_links` + CLIENT_DEFAULTS merge; grading example JSON from spec
- Modify: `docs/src/content/docs/client/panels/form.mdx` if it mentions scope overrides
- Modify: `docs/src/content/docs/orm/data_model/tasks.mdx` — claim + assignee filter briefly

- [ ] **Step 1: Update docs to match spec examples**

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs: TaskConfig client defaults merge, schema-only scope, subtask claim
EOF
)"
```

---

## Task 11: Manual verification checklist

- [ ] Grading TaskDefinition config includes `"update_subtask_image_links": true` in the environment under test (DB seed / import).
- [ ] Open subtask viewer → browser overlay → checkbox **checked**.
- [ ] Grade on unclaimed subtask → FormAnnotation created once; subtask shows current user as assignee.
- [ ] Second Grade / Open grading → same annotation (no duplicate).
- [ ] Task page: Claim one row; Claim all unassigned on page; filter Unassigned / Mine / named assignee.
- [ ] Second user cannot claim already-assigned (409 / no steal); comments by second user do not steal.

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| CLIENT_DEFAULTS + merge, array replace | 1–2 |
| Drop form_entity_scope / form_image_scope | 2, 10 |
| Quick-form triple + lowest id | 3 |
| Image-links checkbox default | 4 |
| claim_if_unassigned repository | 5 |
| Auto-claim FA/Seg create + comments PATCH | 6 |
| Explicit claim + 409 | 7 |
| List filters + assignees + creator DTO | 8 |
| Claim UI + page batch + filters | 9 |
| Docs | 10 |
| Manual | 11 |
| Non-goals (unclaim, tag SubTask, whole-task batch, DB unique) | omitted by design |
