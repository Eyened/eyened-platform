# Keypoint Form Widget & Shared Point Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let FormSchemas declare image keypoints with `"x-eyened-widget": "point"`, edit them from SchemaForm via an Activate control that arms a shared `PointTool` on the main viewer, and make ETDRS/Registration thin wrappers over that same tool.

**Architecture:** Pure `pointSchema` helpers infer single vs list and bare vs `PublicID`-map storage from JSON Schema + entity type. Pure mutation helpers drive place/drag/delete/enum-cycle. `PointTool` is one Overlay. `PointField` is the SchemaForm widget. Forms open in a popup without Svelte parent context, so `openFormInNewWindow` passes the opener’s `ViewerContext` as a prop; a small module-level arming registry ensures only one point field is armed across Form popup and dedicated panels.

**Tech Stack:** SvelteKit 5 (runes), TypeScript, Vitest, existing `Overlay` / `ViewerContext.addOverlay`, `setFormAnnotationValue`, FormSchema JSON seeds.

## Global Constraints

Copied from `docs/superpowers/specs/2026-07-24-keypoint-form-widget-design.md`. Every task implicitly includes these:

- **Marker:** only `"x-eyened-widget": "point"` — no `point-set` widget; cardinality from JSON Schema (`object` vs `array` / `additionalProperties`).
- **Storage:** ImageInstance → bare point or array; other entity types → `{ "<PublicID>": point | point[] }` (API `image_id` / `instance.id` is PublicID).
- **One shared `PointTool`** for Form, ETDRS, Registration; LMB place/replace, RMB delete; ETDRS arms fovea or disc (+ optional `f`/`d` shortcuts).
- **No** new Annotation entity, server validator changes, Affine/RegistrationSet rework, or CFKeypoints changes.
- **Tests:** Vitest for pure helpers/mutations; manual checklist for UI/panels.
- **Commands:** run from `client/` — `npm test`, `npm run check`. Builtin schema JSON lives under `orm/eyened_orm/form_schemas/`; reseed with update for existing DBs.

---

## File structure

| File | Responsibility |
|------|----------------|
| `client/src/lib/forms/schemaType.ts` | Add optional `x-eyened-widget` / `x-eyened-point-mode` on `JSONSchema` |
| `client/src/lib/forms/pointSchema.ts` | Detect widget, analyze shape, get/set points for current PublicID |
| `client/src/lib/forms/pointSchema.test.ts` | Unit tests for helpers |
| `client/src/lib/forms/pointMutations.ts` | Pure place/delete/cycle/drag updates on a point list |
| `client/src/lib/forms/pointMutations.test.ts` | Unit tests for mutations |
| `client/src/lib/forms/pointArming.svelte.ts` | Module singleton: which field is armed; dispose previous tool |
| `client/src/lib/viewer/tools/PointTool.ts` | Overlay: pointer/keyboard → mutations → adapter callback |
| `client/src/lib/forms/PointField.svelte` | Activate UI + summary + extras editors |
| `client/src/lib/forms/SchemaForm.svelte` | Branch to `PointField` when widget is `point` |
| `client/src/lib/viewer-window/panelForm/FormItemContent.svelte` | Accept optional `viewerContext`; setContext for PointField |
| `client/src/lib/viewer-window/panelForm/openFormInNewWindow.ts` | Pass `viewerContext` into popup |
| `client/src/lib/viewer-window/panelForm/FormItem.svelte` | Pass viewer when opening |
| `client/src/lib/viewer-window/panelQuickForm/PanelQuickForm.svelte` | Pass viewer when opening |
| `orm/.../etdrs_grid_coordinates.json` | Add `x-eyened-widget: point` on landmarks |
| `orm/.../pointset_registration.json` | Add root `x-eyened-widget` + `x-eyened-point-mode: registration` |
| `client/.../panelETRDS/*` | Arm PointTool per landmark; keep grid overlay; drop ETDRSGridTool |
| `client/.../panelRegistration/*` | Arm PointTool in registration mode; drop RegistrationTool |
| `client/src/lib/viewer/viewer-utils.ts` | Add `"point"` to `ToolName`; remove obsolete names when unused |
| `docs/src/content/docs/orm/form_schemas.mdx` | Document `x-eyened-widget` |

---

### Task 0: Confirm baseline

- [ ] **Step 1: Confirm client tests pass**

Run: `cd client && npm test`

Expected: existing suite green.

- [ ] **Step 2: Commit nothing** — baseline only.

---

### Task 1: `pointSchema` helpers

**Files:**
- Modify: `client/src/lib/forms/schemaType.ts`
- Create: `client/src/lib/forms/pointSchema.ts`
- Test: `client/src/lib/forms/pointSchema.test.ts`

**Interfaces:**
- Consumes: `JSONSchema`, `FormEntityScope` pattern (`"ImageInstance" | …`).
- Produces:
  - `EYENED_POINT_WIDGET = "point"`
  - `ImagePoint = { x: number; y: number } & Record<string, unknown>`
  - `PointCardinality = "single" | "list"`
  - `PointStorageMode = "bare" | "byPublicId"`
  - `PointSchemaAnalysis` (see below)
  - `isPointWidget(schema: JSONSchema): boolean`
  - `analyzePointSchema(schema, entityType): PointSchemaAnalysis | null`
  - `getPointsForImage(fieldValue, publicId, analysis): (ImagePoint | null)[]`
  - `setPointsForImage(fieldValue, publicId, points, analysis): unknown`

```typescript
export type PointSchemaAnalysis = {
    cardinality: PointCardinality;
    storageMode: PointStorageMode;
    /** Schema for one point object (items or the object itself). */
    pointObjectSchema: JSONSchema;
    registrationMode: boolean;
    enumExtras: { key: string; values: readonly string[] }[];
};
```

- [ ] **Step 1: Write the failing tests**

Create `client/src/lib/forms/pointSchema.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import {
    analyzePointSchema,
    getPointsForImage,
    isPointWidget,
    setPointsForImage,
} from "./pointSchema";
import type { JSONSchema } from "./schemaType";

const pointObject: JSONSchema = {
    type: "object",
    properties: {
        x: { type: "number" },
        y: { type: "number" },
        severity: { type: "string", enum: ["mild", "severe"] },
    },
    required: ["x", "y"],
};

describe("isPointWidget", () => {
    it("detects x-eyened-widget point", () => {
        expect(isPointWidget({ "x-eyened-widget": "point", ...pointObject })).toBe(true);
        expect(isPointWidget(pointObject)).toBe(false);
    });
});

describe("analyzePointSchema", () => {
    it("ImageInstance single object → bare single", () => {
        const a = analyzePointSchema(
            { "x-eyened-widget": "point", ...pointObject },
            "ImageInstance",
        );
        expect(a).toMatchObject({
            cardinality: "single",
            storageMode: "bare",
            registrationMode: false,
        });
        expect(a!.enumExtras).toEqual([{ key: "severity", values: ["mild", "severe"] }]);
    });

    it("ImageInstance array → bare list", () => {
        const a = analyzePointSchema(
            {
                "x-eyened-widget": "point",
                type: "array",
                items: pointObject,
            },
            "ImageInstance",
        );
        expect(a).toMatchObject({ cardinality: "list", storageMode: "bare" });
    });

    it("Eye map of arrays → byPublicId list + registrationMode", () => {
        const a = analyzePointSchema(
            {
                "x-eyened-widget": "point",
                "x-eyened-point-mode": "registration",
                type: "object",
                additionalProperties: {
                    type: "array",
                    items: {
                        oneOf: [pointObject, { type: "null" }],
                    },
                },
            },
            "Eye",
        );
        expect(a).toMatchObject({
            cardinality: "list",
            storageMode: "byPublicId",
            registrationMode: true,
        });
    });

    it("returns null when widget present but shape is not point-like", () => {
        expect(
            analyzePointSchema(
                { "x-eyened-widget": "point", type: "string" },
                "ImageInstance",
            ),
        ).toBeNull();
    });
});

describe("get/setPointsForImage", () => {
    const bareSingle = analyzePointSchema(
        { "x-eyened-widget": "point", ...pointObject },
        "ImageInstance",
    )!;
    const mapList = analyzePointSchema(
        {
            "x-eyened-widget": "point",
            type: "object",
            additionalProperties: { type: "array", items: pointObject },
        },
        "Eye",
    )!;

    it("bare single round-trip", () => {
        const pts = [{ x: 1, y: 2 }];
        const value = setPointsForImage(undefined, "img-a", pts, bareSingle);
        expect(value).toEqual({ x: 1, y: 2 });
        expect(getPointsForImage(value, "img-a", bareSingle)).toEqual([{ x: 1, y: 2 }]);
        expect(setPointsForImage(value, "img-a", [], bareSingle)).toBeUndefined();
    });

    it("byPublicId list round-trip", () => {
        const value = setPointsForImage({}, "img-a", [{ x: 1, y: 2 }], mapList);
        expect(value).toEqual({ "img-a": [{ x: 1, y: 2 }] });
        expect(getPointsForImage(value, "img-a", mapList)).toEqual([{ x: 1, y: 2 }]);
        expect(getPointsForImage(value, "img-b", mapList)).toEqual([]);
    });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd client && npx vitest run src/lib/forms/pointSchema.test.ts`

Expected: FAIL (module not found / exports missing).

- [ ] **Step 3: Extend JSONSchema type**

In `client/src/lib/forms/schemaType.ts`, add to `JSONSchema`:

```typescript
    /** Eyened UI widget hint (ignored by jsonschema validators). */
    "x-eyened-widget"?: "point" | (string & {});
    /** Optional point-tool mode (e.g. registration null-slots). */
    "x-eyened-point-mode"?: "registration" | (string & {});
```

- [ ] **Step 4: Implement `pointSchema.ts`**

Create `client/src/lib/forms/pointSchema.ts` implementing the interfaces above.

Rules:
- `isPointWidget`: `(schema as any)["x-eyened-widget"] === "point"`.
- `storageMode`: `"bare"` iff `entityType === "ImageInstance"`, else `"byPublicId"`.
- Cardinality: if schema `type === "array"` → list; if `additionalProperties` is array (or array oneOf) → list; if object with `properties.x` and `properties.y` → single; if `additionalProperties` is point object → single; else null.
- For map schemas, `pointObjectSchema` comes from `additionalProperties.items` (unwrap `oneOf` null) or `additionalProperties` itself.
- `enumExtras`: from `pointObjectSchema.properties` entries that have `enum` string arrays (skip `x`/`y`).
- `registrationMode`: `schema["x-eyened-point-mode"] === "registration"`.
- `getPointsForImage`: always return an array (0–1 elements for single). Preserve `null` entries for registration lists.
- `setPointsForImage`: for bare single, write object or `undefined` if empty; for bare list, write array; for maps, clone object and set/delete key when empty list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd client && npx vitest run src/lib/forms/pointSchema.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add client/src/lib/forms/schemaType.ts client/src/lib/forms/pointSchema.ts client/src/lib/forms/pointSchema.test.ts
git commit -m "$(cat <<'EOF'
feat(forms): add pointSchema helpers for x-eyened-widget point fields

EOF
)"
```

---

### Task 2: Pure point mutations

**Files:**
- Create: `client/src/lib/forms/pointMutations.ts`
- Test: `client/src/lib/forms/pointMutations.test.ts`

**Interfaces:**
- Consumes: `ImagePoint`, `PointCardinality` from `pointSchema.ts`.
- Produces:
  - `placePoint(points, position, cardinality, registrationMode): (ImagePoint | null)[]`
  - `deletePointAt(points, index, registrationMode): (ImagePoint | null)[]`
  - `movePointAt(points, index, position): (ImagePoint | null)[]`
  - `cycleEnumExtra(point, key, values): ImagePoint`

- [ ] **Step 1: Write the failing tests**

```typescript
import { describe, it, expect } from "vitest";
import {
    cycleEnumExtra,
    deletePointAt,
    movePointAt,
    placePoint,
} from "./pointMutations";

describe("placePoint", () => {
    it("single replaces", () => {
        expect(placePoint([{ x: 1, y: 1 }], { x: 9, y: 9 }, "single", false)).toEqual([
            { x: 9, y: 9 },
        ]);
        expect(placePoint([], { x: 9, y: 9 }, "single", false)).toEqual([{ x: 9, y: 9 }]);
    });

    it("list appends", () => {
        expect(placePoint([{ x: 1, y: 1 }], { x: 2, y: 2 }, "list", false)).toEqual([
            { x: 1, y: 1 },
            { x: 2, y: 2 },
        ]);
    });

    it("registration fills first null slot", () => {
        const pts = [{ x: 1, y: 1 }, null, { x: 3, y: 3 }] as const;
        expect(placePoint([...pts], { x: 2, y: 2 }, "list", true)).toEqual([
            { x: 1, y: 1 },
            { x: 2, y: 2 },
            { x: 3, y: 3 },
        ]);
    });
});

describe("deletePointAt", () => {
    it("splices in normal list mode", () => {
        expect(
            deletePointAt([{ x: 1, y: 1 }, { x: 2, y: 2 }], 0, false),
        ).toEqual([{ x: 2, y: 2 }]);
    });

    it("nulls mid-list in registration mode; splices last", () => {
        expect(
            deletePointAt([{ x: 1, y: 1 }, { x: 2, y: 2 }], 0, true),
        ).toEqual([null, { x: 2, y: 2 }]);
        expect(
            deletePointAt([{ x: 1, y: 1 }, { x: 2, y: 2 }], 1, true),
        ).toEqual([{ x: 1, y: 1 }]);
    });
});

describe("movePointAt / cycleEnumExtra", () => {
    it("moves and cycles", () => {
        expect(movePointAt([{ x: 1, y: 1 }], 0, { x: 5, y: 6 })).toEqual([{ x: 5, y: 6 }]);
        expect(cycleEnumExtra({ x: 1, y: 1 }, "severity", ["a", "b"])).toEqual({
            x: 1,
            y: 1,
            severity: "a",
        });
        expect(
            cycleEnumExtra({ x: 1, y: 1, severity: "a" }, "severity", ["a", "b"]),
        ).toEqual({ x: 1, y: 1, severity: "b" });
    });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd client && npx vitest run src/lib/forms/pointMutations.test.ts`

Expected: FAIL.

- [ ] **Step 3: Implement mutations**

Mirror RegistrationTool behavior for registration delete/place; single mode always length 0 or 1; `cycleEnumExtra` advances to next enum value (wrap), defaulting to first when missing.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/forms/pointMutations.ts client/src/lib/forms/pointMutations.test.ts
git commit -m "$(cat <<'EOF'
feat(forms): add pure point list mutations for PointTool

EOF
)"
```

---

### Task 3: `PointTool` Overlay + arming registry

**Files:**
- Create: `client/src/lib/viewer/tools/PointTool.ts`
- Create: `client/src/lib/forms/pointArming.svelte.ts`
- Modify: `client/src/lib/viewer/viewer-utils.ts` (`ToolName` add `"point"`)

**Interfaces:**
- Consumes: mutations, `PointSchemaAnalysis`, `ViewerContext`, `Overlay`.
- Produces:
  - `PointTool` class implementing `Overlay`
  - `pointArming.arm({ key, createTool })` / `pointArming.disarm(key?)` / `pointArming.isArmed(key)`

```typescript
export type PointToolOptions = {
    canEdit: boolean;
    analysis: PointSchemaAnalysis;
    label: string;
    /** Current image PublicID (reactive: tool may read via getter). */
    getPublicId: () => string;
    getFieldValue: () => unknown;
    setFieldValue: (next: unknown) => void;
    /** Optional: place single landmark at cursor without click (ETDRS f/d). */
    // handled by callers via setFieldValue + mutations, not required on tool
};
```

Constructor stores options. On pointer events (ignore `shiftKey`):
- LMB empty → `placePoint` then `setPointsForImage` → `setFieldValue`
- LMB hit → start drag; pointermove updates via `movePointAt`
- RMB hit → `deletePointAt`
- keydown `e` (or first enum extra): `cycleEnumExtra` on hovered/selected point
- `repaint`: draw markers for `getPointsForImage` on current publicId (skip nulls); show index for lists; show enum extra text when present

`pointArming.svelte.ts`:

```typescript
type Armed = { key: string; dispose: () => void };

class PointArming {
    armed: Armed | null = $state(null);

    arm(key: string, attach: () => () => void) {
        if (this.armed?.key === key) {
            this.disarm();
            return;
        }
        this.disarm();
        this.armed = { key, dispose: attach() };
    }

    disarm(key?: string) {
        if (key && this.armed?.key !== key) return;
        this.armed?.dispose();
        this.armed = null;
    }

    isArmed(key: string) {
        return this.armed?.key === key;
    }
}

export const pointArming = new PointArming();
```

- [ ] **Step 1: Add `"point"` to `ToolName` in `viewer-utils.ts`**

- [ ] **Step 2: Implement `PointTool.ts`** — port hit-testing/paint patterns from `Registration.ts` (radius ~16, cross or rect). Do not call `setFormAnnotationValue` inside the tool; only `setFieldValue` so callers control persistence.

- [ ] **Step 3: Implement `pointArming.svelte.ts`**

- [ ] **Step 4: Smoke-compile**

Run: `cd client && npx vitest run src/lib/forms/pointSchema.test.ts src/lib/forms/pointMutations.test.ts`

Expected: PASS (no regressions).

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer/tools/PointTool.ts client/src/lib/forms/pointArming.svelte.ts client/src/lib/viewer/viewer-utils.ts
git commit -m "$(cat <<'EOF'
feat(viewer): add shared PointTool and point field arming registry

EOF
)"
```

---

### Task 4: `PointField` + SchemaForm branch

**Files:**
- Create: `client/src/lib/forms/PointField.svelte`
- Modify: `client/src/lib/forms/SchemaForm.svelte`

**Interfaces:**
- Consumes: `analyzePointSchema`, `pointArming`, `PointTool`, Svelte `viewerContext` (optional), props `schema`, `value`, `onchange`, `canEdit`, plus **parent-provided** `entityType` and `fieldPath` (see below).
- Produces: UI that arms/disarms `PointTool`.

**SchemaForm prop plumbing:** add optional props (default undefined) and pass through recursion:

```typescript
entityType?: FormSchemaGET["entity_type"] | null;
fieldPath?: string; // e.g. "" at root, "fovea" nested
```

When rendering a child object property `key`, pass `fieldPath: fieldPath ? `${fieldPath}.${key}` : key`.

For point widget branch (before generic object/array):

```svelte
{:else if isPointWidget(schema)}
    <PointField
        {schema}
        {value}
        {onchange}
        {canEdit}
        entityType={entityType ?? "ImageInstance"}
        fieldPath={fieldPath ?? schema.title ?? "point"}
    />
```

**PointField.svelte** behavior:
- `analysis = analyzePointSchema(schema, entityType)` — if null, show warning text and raw JSON.stringify summary; no Activate.
- Summary: count of points on current image / coords.
- Get `viewerContext` via `getContext<ViewerContext | undefined>("viewerContext")` (may be undefined).
- Activate button enabled when `canEdit && viewerContext && analysis`.
- On Activate: `pointArming.arm(fieldPath + ":" + annotationId?, () => viewerContext.addOverlay(new PointTool(...)))`  
  - Persistence: `setFieldValue` calls `onchange(next)` only (parent FormItemContent debounces `setFormAnnotationValue`).
- Clear button: `onchange(setPointsForImage(value, publicId, [], analysis))` or unset.
- For each `enumExtras` / string props on selected point: simple selects/inputs that update via get/set helpers.
- If no viewer: hide Activate; still show summary + extras if editable values exist without tool.

`PointTool` needs `getPublicId: () => viewerContext.image.instance.id`.

- [ ] **Step 1: Implement `PointField.svelte`**

- [ ] **Step 2: Wire SchemaForm branch + prop pass-through for `entityType` / `fieldPath`**

- [ ] **Step 3: Run unit tests**

Run: `cd client && npm test`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add client/src/lib/forms/PointField.svelte client/src/lib/forms/SchemaForm.svelte
git commit -m "$(cat <<'EOF'
feat(forms): render PointField for x-eyened-widget point schemas

EOF
)"
```

---

### Task 5: Pass `ViewerContext` into form popup

**Files:**
- Modify: `client/src/lib/viewer-window/panelForm/FormItemContent.svelte`
- Modify: `client/src/lib/viewer-window/panelForm/openFormInNewWindow.ts`
- Modify: `client/src/lib/viewer-window/panelForm/FormItem.svelte`
- Modify: `client/src/lib/viewer-window/panelQuickForm/PanelQuickForm.svelte`
- Modify: `client/src/lib/viewer-window/panelForm/FormItemContent.svelte` (SchemaForm `entityType`)

**Why:** `openNewWindow` mounts FormItemContent as a root — no Svelte `viewerContext` ancestor. Pass the opener’s `ViewerContext` as a prop and `setContext("viewerContext", viewerContext)` so PointField can arm overlays on the live viewer.

- [ ] **Step 1: Extend `openFormInNewWindow`**

```typescript
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";

export function openFormInNewWindow(
    form: FormAnnotationGET,
    canEdit: boolean,
    viewerContext?: ViewerContext,
): Window {
    // ...
    openWindow = openNewWindow(
        FormItemContent,
        { form, canEdit, viewerContext },
        title,
    );
    return openWindow;
}
```

- [ ] **Step 2: FormItemContent props + context**

```svelte
import { setContext } from "svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { formSchemas } from "$lib/data";

interface Props {
    form: FormAnnotationGET;
    canEdit: boolean;
    viewerContext?: ViewerContext;
}
let { form, canEdit, viewerContext }: Props = $props();

if (viewerContext) {
    setContext("viewerContext", viewerContext);
}
setContext("pointFormAnnotationId", form.id);

const formSchema = $derived(formSchemas.get(form.form_schema_id)!);
// pass entityType={formSchema.entity_type} into SchemaForm
```

In `PointField`, `getContext<number>("pointFormAnnotationId")` (optional) to build arming keys like `` `form:${id}:${fieldPath}` ``.

- [ ] **Step 3: Call sites pass `viewerContext`**

In `FormItem.svelte` and `PanelQuickForm.svelte`, `getContext<ViewerContext>("viewerContext")` and pass into `openFormInNewWindow(form, canEdit, viewerContext)`.

- [ ] **Step 4: On popup `beforeunload`, `pointArming.disarm()`** — extend `openFormInNewWindow` / mount cleanup so closing the form releases the tool.

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/panelForm/FormItemContent.svelte \
  client/src/lib/viewer-window/panelForm/openFormInNewWindow.ts \
  client/src/lib/viewer-window/panelForm/FormItem.svelte \
  client/src/lib/viewer-window/panelQuickForm/PanelQuickForm.svelte
git commit -m "$(cat <<'EOF'
feat(forms): pass ViewerContext into form popup for point tool arming

EOF
)"
```

---

### Task 6: Builtin schema markers + docs

**Files:**
- Modify: `orm/eyened_orm/form_schemas/etdrs_grid_coordinates.json`
- Modify: `orm/eyened_orm/form_schemas/pointset_registration.json`
- Modify: `docs/src/content/docs/orm/form_schemas.mdx`

- [ ] **Step 1: Update ETDRS JSON**

Add `"x-eyened-widget": "point"` to `fovea` and `disc_edge` property schemas (keep `x`/`y` required).

- [ ] **Step 2: Update Pointset registration JSON**

On the root object add:

```json
"x-eyened-widget": "point",
"x-eyened-point-mode": "registration"
```

Keep `additionalProperties` array with `{x,y}` / `null` oneOf.

- [ ] **Step 3: Document in `form_schemas.mdx`**

Add a short section: client UI extension `x-eyened-widget: point`; cardinality from JSON Schema; ImageInstance vs map storage; `x-eyened-point-mode: registration`; note `eorm seed-form-schemas --update` (or project’s equivalent) to refresh builtin rows.

- [ ] **Step 4: Commit**

```bash
git add orm/eyened_orm/form_schemas/etdrs_grid_coordinates.json \
  orm/eyened_orm/form_schemas/pointset_registration.json \
  docs/src/content/docs/orm/form_schemas.mdx
git commit -m "$(cat <<'EOF'
feat(orm): mark ETDRS and registration schemas with point widgets

EOF
)"
```

---

### Task 7: Thin ETDRS panel on `PointTool`

**Files:**
- Modify: `client/src/lib/viewer-window/panelETRDS/PanelETDRS.svelte`
- Modify: `client/src/lib/viewer-window/panelETRDS/ETDRSGridItem.svelte`
- Delete (end of task): `client/src/lib/viewer/tools/ETDRSGrid.svelte.ts` after unused

**Behavior change (intentional):** stop LMB→fovea / RMB→disc. Tool toggle arms one landmark field at a time.

- [ ] **Step 1: Replace `ETDRSGridTool` usage**

When tool activates for an annotation, default-arm `"fovea"`. UI on `ETDRSGridItem`: two toggles or a small select — **Fovea** / **Disc** — calling:

```typescript
function armLandmark(annotation: FormAnnotationGET, field: "fovea" | "disc_edge") {
    const key = `etdrs:${annotation.id}:${field}`;
    const analysis = analyzePointSchema(
        /* fovea or disc_edge subschema from etdrsSchema.schema */,
        "ImageInstance",
    )!;
    pointArming.arm(key, () =>
        viewerContext.addOverlay(
            new PointTool({
                canEdit: globalContext.canEdit(annotation),
                analysis,
                label: field,
                getPublicId: () => instance.id,
                getFieldValue: () => (annotation.form_data as any)?.[field],
                setFieldValue: (next) => {
                    const form_data = { ...(annotation.form_data || {}), [field]: next };
                    annotation.form_data = form_data;
                    setFormAnnotationValue(annotation.id, form_data);
                },
            }),
        ),
    );
}
```

Keep `ETDRSGridItemOverlay` for grid rings unchanged.

- [ ] **Step 2: Shortcuts `f` / `d`**

While an annotation’s tool is active (panel active + tool armed for that annotation), on viewer keydown (via a tiny Overlay or PointTool option `hotkeys?: Record<string, () => void>`):

- `f` → set fovea to `viewerToImageCoordinates(cursor)` (and arm fovea)
- `d` → same for disc_edge

Implement as optional `PointTool` ctor `onKey?: (e: ViewerEvent<KeyboardEvent>) => void` **or** a separate 5-line overlay added alongside the tool in PanelETDRS. Prefer a small `ETDRSHotkeys` overlay in the panel file to avoid bloating PointTool.

- [ ] **Step 3: Update ETDRSGridItem UI** for fovea/disc arming state (highlight which landmark is armed).

- [ ] **Step 4: Remove imports of `ETDRSGridTool`; delete file if unused. Remove `"ETRDS-grid"` from `ToolName` if unused.**

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/panelETRDS/ client/src/lib/viewer/tools/ client/src/lib/viewer/viewer-utils.ts
git commit -m "$(cat <<'EOF'
refactor(etdrs): use shared PointTool with fovea/disc arming and shortcuts

EOF
)"
```

---

### Task 8: Thin Registration panel on `PointTool`

**Files:**
- Modify: `client/src/lib/viewer-window/panelRegistration/PanelRegistration.svelte`
- Modify: `client/src/lib/viewer-window/panelRegistration/RegistrationItem.svelte`
- Delete: `client/src/lib/viewer/tools/Registration.ts` after migration
- Update imports of `PointList` type — move `export type PointList = (Position2D | null)[]` to `pointSchema.ts` or keep a one-line re-export

- [ ] **Step 1: On activate, arm PointTool with registration analysis**

```typescript
const analysis = analyzePointSchema(
    registrationSchema.schema as JSONSchema,
    "Eye",
)!; // expects x-eyened-point-mode registration after Task 6

pointArming.arm(`registration:${formAnnotation.id}`, () =>
    viewerContext.addOverlay(
        new PointTool({
            canEdit,
            analysis,
            label: "registration",
            getPublicId: () => viewerContext.image.instance.id,
            getFieldValue: () => formAnnotation.form_data,
            setFieldValue: (next) => {
                formAnnotation.form_data = next as any;
                setFormAnnotationValue(formAnnotation.id, next);
            },
        }),
    ),
);
```

Preserve digit-key focus: port `RegistrationTool.keyup` number handling into `PointTool` when `analysis.registrationMode` is true (zoom to point index).

- [ ] **Step 2: RegistrationItem** — import `PointList` from new location; behavior otherwise unchanged.

- [ ] **Step 3: Delete `Registration.ts`; remove `"registration"` from `ToolName` if unused.**

- [ ] **Step 4: Commit**

```bash
git add client/src/lib/viewer-window/panelRegistration/ client/src/lib/viewer/tools/ client/src/lib/forms/pointSchema.ts client/src/lib/viewer/viewer-utils.ts
git commit -m "$(cat <<'EOF'
refactor(registration): use shared PointTool for pointset editing

EOF
)"
```

---

### Task 9: Manual verification checklist + final cleanup

**Files:** none required beyond leftover import fixes.

- [ ] **Step 1: Run full client tests**

Run: `cd client && npm test`

Expected: PASS.

- [ ] **Step 2: Manual checklist** (dev environment with seeded schemas updated)

1. **Form popup:** schema with `"x-eyened-widget": "point"` on an ImageInstance field → Activate → LMB place, drag, RMB delete → value persists after reload.
2. **List field:** array of points → multiple markers; extras enum cycles with `e` (or chosen key).
3. **Eye-scoped map:** place on image A, switch image, place on B → both PublicID keys present.
4. **ETDRS:** arm fovea vs disc; `f`/`d` shortcuts; grid overlay still draws when both points set.
5. **Registration:** numbered points, null mid-list on RMB, digit focus; switch image updates the active list.
6. **Exclusive arming:** Activate in form then arm ETDRS → previous tool disposed.
7. **Wrong image (ImageInstance):** form for image A, viewer on B → Activate disabled or writes refused with hint (per spec).

- [ ] **Step 3: Fix any issues found; commit fixes as needed**

- [ ] **Step 4: Final commit if docs/checklist notes added** (optional)

```bash
git status
# only commit if there are intentional leftover fixes
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| `x-eyened-widget: point` only; cardinality from JSON Schema | 1, 4, 6 |
| Bare vs PublicID map by entity type | 1 |
| Per-point extras / enum cycle | 1, 2, 3, 4 |
| SchemaForm Activate → main viewer tool | 4, 5 |
| Shared PointTool | 3, 7, 8 |
| ETDRS thin wrapper + f/d + no LMB/RMB dual | 7 |
| Registration thin wrapper + null slots | 8 |
| Dual shapes / no FormData migration | 1, 6 |
| Unit tests helpers/mutations | 1, 2 |
| Manual UI checks | 9 |
| Popup lacks Svelte context → pass ViewerContext | 5 |
| Docs for widget | 6 |
| Non-goals (no server validator / new Annotation / Affine) | respected |

## Type consistency notes

- Image key is always `instance.id` / FormAnnotation `image_id` (PublicID string).
- Tool never persists directly except when panel adapters call `setFormAnnotationValue`; Form popup uses `onchange` → debounced save.
- `pointArming` keys must be unique per annotation+field (`etdrs:12:fovea`, `registration:12`, `form:12:lesions`).
