# Keypoint Form Widget & Shared Point Tool — Design

**Date:** 2026-07-24  
**Status:** Approved design (brainstorming)  
**GitHub:** [Eyened/eyened-platform#113](https://github.com/Eyened/eyened-platform/issues/113)  
**Scope:** Generic image keypoints as FormSchema fields (`x-eyened-widget`), SchemaForm tool activation, shared `PointTool`, thin ETDRS/Registration panels

## Context

There is no general way to place individual keypoints on images from clinical forms. Segmentation is a poor substitute for adjustable landmarks. ETDRS and registration already store `{x,y}` (and per-image point lists) in `FormAnnotation.FormData`, but each has a dedicated panel and tool. The Form panel’s `SchemaForm` only renders plain JSON Schema types and cannot arm a viewer tool.

## Goals

- Declare point / point-set fields in FormSchemas via `x-eyened-widget`.
- Support common cases: one landmark, or a list of landmarks sharing the field label; optional per-point extras (enum / free-text).
- Store image identity when the form is not ImageInstance-scoped (`PublicID` map).
- Show an Activate control in SchemaForm that arms a tool in the main viewer.
- One shared `PointTool` for Form panel, ETDRS, and Registration; existing panels become thin wrappers (no generic form popup for those builtins).
- Prefer dual value shapes so ETDRS and registration data stay readable without a forced migration.

## Non-goals

- New Annotation / mask entity for keypoints.
- Server-side semantics for `x-eyened-*` (validator ignores vendor extensions).
- Reworking Affine registration or RegistrationSet UIs.
- Changing AI `CFKeypoints` on `ImageInstance`.
- Automated canvas / Playwright coverage in v1.

---

## 1. Architecture

Three shared pieces:

1. **`pointSchema` helpers** — Detect `x-eyened-widget`, classify single vs set, wrap/unwrap ImageInstance vs `PublicID` map, describe per-point extras for UI/tool.
2. **`PointTool` (Overlay)** — Place, drag, delete, cycle enum extras on the current viewer image. Writes through an adapter (get/set points for the current image). Used by Form, ETDRS, and Registration.
3. **`PointField` UI** — Activate toggle, value summary, editors for non-spatial extras. Mounted by `SchemaForm` when the widget marker is present; also composed by thin panels.

`SchemaForm` stays a schema renderer: it does not talk to the viewer directly. Viewer access is injected via Svelte context from the panel/window into `PointField` / tool setup.

```text
FormSchema (x-eyened-widget)
        │
        ▼
 SchemaForm ──► PointField ──► PointTool (Overlay)
                    │                │
                    │                ▼
                    └── onchange ► FormData ► setFormAnnotationValue
```

---

## 2. Schema contract & value shapes

### Marker

On the field schema:

| Value | Meaning |
|-------|---------|
| `"x-eyened-widget": "point"` | Single landmark |
| `"x-eyened-widget": "point-set"` | List of landmarks |

### Point object

Always `x` and `y` (full-resolution image pixels). Additional properties come from normal JSON Schema on that object (e.g. `severity` enum, `note` string). Enums can be cycled in the tool; strings (and enums) are editable in `PointField`.

### Storage by entity scope

| Form entity | Widget | Stored value |
|-------------|--------|--------------|
| ImageInstance | `point` | `{ x, y, …extras }` |
| ImageInstance | `point-set` | `[ { x, y, … }, … ]` |
| Other (Eye, Study, …) | `point` | `{ "<publicId>": { x, y, … } }` |
| Other | `point-set` | `{ "<publicId>": [ { x, y, … }, … ] }` |

Helpers always present the tool with “points for the current image”; wrap/unwrap depends on `FormSchema.EntityType` (or equivalent scope).

### Builtin schemas

- **ETDRS-grid coordinates** — ImageInstance; `fovea` / `disc_edge` as `point` widgets; data remains bare `{x,y}`.
- **Pointset registration** — Eye-level map `publicId →` arrays. The **root** schema carries `"x-eyened-widget": "point-set"` (there is no named field; `additionalProperties` defines each image’s array). Registration mode (`null` slots, numbered focus) is a tool/adapter flag, not required for generic clinical schemas.

### Validation

Server/ORM keep Draft-07 `jsonschema`. `x-eyened-*` is ignored by the validator. Client helpers drive UI and tool behavior only.

---

## 3. `PointTool` behavior

Configured by the armed field: widget mode, extras schema, value adapter, `canEdit`.

### Interactions (all consumers)

- **LMB empty** — place (for `point`, replace the single value; for `point-set`, append).
- **LMB on point** — select / drag.
- **RMB on point** — delete (registration mode: clear to `null` when mid-list; otherwise splice).
- **Shift** — ignored (pan/zoom), same as today.
- **Enum extra** — while hovered/selected, a dedicated key (or scroll) cycles the enum; show current value near the marker.
- **Paint** — markers for points on the **current viewer image** only; field title + optional extra; indices for sets.

### ETDRS simplification

ETDRS no longer uses LMB→fovea / RMB→disc. Same tool as everywhere. The panel arms either `fovea` or `disc_edge`. Optional shortcuts when the panel/annotation is active: `f` / `d` place (or move) that landmark at the current cursor position.

### Registration mode

`point-set` on a `PublicID` map; keep numbered markers, `null` slots, and digit-key focus around a point.

### Activation

At most one point field armed per viewer window. Activating disposes any previous point tool. Read-only: paint only.

Persistence goes through existing `setFormAnnotationValue` (Form panel debounce unchanged; dedicated panels may save immediately as today).

---

## 4. `PointField` + SchemaForm

### `PointField`

- Title/description, compact value summary.
- **Activate tool** when `canEdit` and a viewer image is available; otherwise disabled with a tooltip.
- Editors for non-spatial extras on the point object.
- Clear control (unset field, or clear points for the current image in map mode).

### SchemaForm

If `schema["x-eyened-widget"]` is `point` or `point-set`, render `PointField` instead of generic object/array UI. Still call `onchange` with the updated field value so FormItemContent’s save path is unchanged.

### Viewer context

Form / QuickForm (and thin panels) provide context such as:

- viewer access / `addOverlay`
- current image `PublicID`
- entity scope / whether values are map-keyed
- form annotation identity for saves
- `armedFieldPath` (one armed field per window)

Without viewer context (e.g. detached form with no viewer): show values read-only; hide Activate.

---

## 5. Thin wrapper panels

Panels keep list/create/filter chrome and **domain-specific overlays**. Point editing uses `PointField` + `PointTool`. Builtin schemas remain hidden from the generic Form panel (`HIDE_FROM_FORM_PANEL_NAMES`); the specialized panel is the UI.

### ETDRS

- Add widget markers on `fovea` / `disc_edge`.
- Arm Fovea or Disc per annotation; `f` / `d` shortcuts as above.
- Keep `ETDRSGridItemOverlay` for grid rings from `form_data`.
- Remove `ETDRSGridTool` once `PointTool` covers placement.

### Registration

- Mark per-image arrays as `point-set` (map-by-`PublicID` unchanged).
- Activating an annotation arms `PointTool` in registration mode for the current image’s list.
- Remove `RegistrationTool` after parity.

### New clinical schemas

Any non-hidden schema with point widgets works from Form / QuickForm with Activate; no dedicated panel required.

---

## 6. Data flow & edge cases

1. Edit via tool or `PointField` → local value via `onchange`.
2. Persist with `setFormAnnotationValue`.
3. Helpers wrap/unwrap so the tool only sees current-image points.
4. Switching viewer image rebinds the adapter to the new `PublicID` (map mode).

| Case | Behavior |
|------|----------|
| No viewer / no image | Activate disabled; values visible |
| ImageInstance form, viewer on another image | Do not write; clear UI hint; linked-image overlays only where panels already support them |
| Partial points | Tool writes complete `{x,y}` only; schema validation for required props |
| Multiple Activate | Last armed field wins |

---

## 7. Testing

**Unit — `pointSchema` helpers:** widget detection; wrap/unwrap; single replace vs set append/delete; registration null-clear vs splice; enum cycle order.

**Unit — tool adapter:** mock get/set + synthetic pointer actions → assert `FormData` for ETDRS-like and registration-like fixtures (no WebGL).

**Manual:** Form panel Activate place/drag/delete + reload; ETDRS arm + shortcuts + grid overlay; Registration numbers/nulls + image switch.

No pixel screenshot suite in v1.

---

## Success criteria

- A FormSchema can declare `point` / `point-set` with `x-eyened-widget` and optional per-point extras; graders place and edit points from the Form panel via Activate.
- Multi-image scopes record `PublicID` keys; ImageInstance scopes keep bare coordinates.
- ETDRS and Registration use the same `PointTool`; ETDRS placement is LMB/RMB-simple with panel arming + `f`/`d`.
- Existing ETDRS and registration `FormData` shapes remain valid without migration.
