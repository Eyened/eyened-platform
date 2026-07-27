# Keypoint Arming Simplification — Design

**Date:** 2026-07-27  
**Status:** Approved design (brainstorming)  
**Builds on:** [2026-07-24-keypoint-form-widget-design.md](./2026-07-24-keypoint-form-widget-design.md)  
**Scope:** Simplify the client mental model for form/panel keypoints — unified arming, one tool per session, adapters at the FormData boundary. No FormData migration.

## Context

The keypoint form widget works, but the implementation has several competing models:

- Two arming APIs (`arm` attach/dispose vs `armForm` + MainViewer mount)
- ETDRS mounts two `PointTool`s with sibling hit-testing and placement-target flags
- Registration and forms each hand-wire tools differently
- `PointTool` options encode host/sibling/placement concerns that only exist because of dual tools

Goal: same UX and same stored FormData shapes, with a simpler operational model. Prefer net less code where complexity collapses, but the primary win is fewer concepts.

## Goals

- One arming API and one exclusive point session.
- One `PointTool` per mounted viewer for the armed session (shared adapter).
- Adapters map that list to existing FormData (bare / byPublicId / registration nulls / ETDRS fields).
- Preserve ETDRS dual-landmark UX (both visible, active slot, `f`/`d` shortcuts) via a MultiField adapter — not two tools.
- Panels keep domain chrome (lists, ETDRS grid) but do not construct `PointTool`.

## Non-goals

- Migrating or unifying stored FormData shapes.
- Stripping PointField’s extras / coordinate editor in this pass.
- Changing Affine registration or RegistrationSet UIs.
- Server/ORM changes to `x-eyened-*`.

---

## 1. Mental model & architecture

**Arm a session → each eligible MainViewer mounts one `PointTool` → each tool edits the same `PointList` via the session adapter → the adapter maps that list to FormData.**

“One tool” means one tool **per viewer**, not one process-wide instance. Form sessions omit `host`, so every open MainViewer mounts a tool against the same adapter. Panel sessions set `host` to that panel’s viewer.

```text
PointField / ETDRS / Registration
        │
        ▼
  pointArming.arm(session)     ← single API
        │
        ▼
  MainViewer(s) each mount one PointTool
        │
        ▼
  PointTool  ↔  adapter.getPoints() / setPoints()
        │
        ▼
  Adapter writes FormAnnotation.form_data
```

### Session

| Field | Role |
|-------|------|
| `key` | Exclusive replace / toggle-disarm |
| `adapter` | Read/write points for current image |
| `style` | Marker appearance |
| `canEdit` | Paint-only when false |
| `host?` | If set, only that viewer mounts; if omitted, every MainViewer mounts (form case) |
| `slotKeys?` | `{ index, key, label }[]` for shortcuts into fixed slots |
| `activeSlot` | Mutable index for MultiField empty-click / UI highlight; hit, drag, or slotKeys update it. Ignored for ordinary FieldAdapter list/single placement. |

### What goes away

- `arm` vs `armForm` and `kind: "panel" | "form"`
- Panel-local `new PointTool` + `addOverlay`
- Dual ETDRS tools, `liveTools` sibling hit-testing, `isPlacementTarget` / `onBecomePlacementTarget`

### What stays

- Existing FormData shapes from the 2026-07-24 design
- PointField Activate / Clear / summary / extras editor
- ETDRS grid overlay and panel list chrome
- Registration null-slot and digit-focus behavior (via FieldAdapter + `registrationMode`)

---

## 2. Adapters

### Contract

```ts
type PointAdapter = {
  analysis: PointSchemaAnalysis;
  getPublicId: () => string;
  getPoints: () => PointList;
  setPoints: (points: PointList) => void;
};
```

The tool never sees field paths, PublicID maps, or multi-field FormData — only a list (nulls allowed).

### FieldAdapter

Wraps one schema field using existing `getPointsForImage` / `setPointsForImage`.

- **Form PointField:** `get`/`set` through the field `value` / `onchange`.
- **Registration:** root `form_data` as byPublicId list with `registrationMode`.

Storage modes and cardinality stay in `pointSchema`; the adapter is a thin binding.

### MultiFieldAdapter (ETDRS)

Fixed named slots on one annotation, e.g. `["fovea", "disc_edge"]`.

- `getPoints` → `[form_data.fovea ?? null, form_data.disc_edge ?? null]`
- `setPoints([a, b])` → write or clear each field on the same `form_data` (match today’s clear semantics when a slot is null)
- Synthetic analysis: list cardinality, registration-like null slots, ImageInstance bare fields
- Labels from slot names
- Empty click **places/replaces `session.activeSlot` only** (not registration’s fill-first-null). Hit, drag, or `slotKeys` update `activeSlot`.
- Session `slotKeys`: `f` → index 0, `d` → index 1

No migration: ETDRS remains `{ fovea, disc_edge }`.

Placement difference vs Registration FieldAdapter:

| Mode | Empty-click placement |
|------|------------------------|
| FieldAdapter + `registrationMode` | Fill first null slot, else append (today’s `placePoint`) |
| MultiFieldAdapter | Write the active slot index only |

---

## 3. Slim `PointTool`

Constructor roughly: `{ canEdit, adapter, label?, style, getActiveSlot?, setActiveSlot? }` plus session-level key wiring for `slotKeys`.

| Removed from tool options | Reason |
|---------------------------|--------|
| Separate get/set field + publicId + analysis | Live on adapter |
| `host`, `liveTools`, sibling hit checks | One tool per viewer; no dual-tool siblings |
| `isPlacementTarget`, `onBecomePlacementTarget` | `session.activeSlot` |
| Per-tool `placeKey` | Session `slotKeys` → place into slot index |

**Kept:** place / drag / delete, OCT `index` tagging and slice visibility, enum cycle (`c`), registration digit-focus when `analysis.registrationMode`, paint.

`pointMutations` remains pure list ops. Add a small `placePointAt(points, index, position, …)` (or equivalent) for MultiField active-slot writes; Registration keeps fill-first-null `placePoint`.

### Mounting (MainViewer)

Each MainViewer reacts to the global session:

1. If no session → nothing.
2. If `session.host` is set and ≠ this `viewerContext` → skip.
3. Else mount one `PointTool` bound to `session.adapter`; wire `slotKeys` to keydown place-into-slot; dispose on change/destroy.

Panels only call `pointArming.arm({ ... })` / `disarm`.

---

## 4. Consumers

### PointField

- Activate → FieldAdapter + arm **without** `host` (all MainViewers).
- Deactivate / Clear / form window close → `disarm`.
- No overlay construction.

### Registration panel

- Activate → FieldAdapter on root form_data, `host: viewerContext`.
- Keep create/filter/list UI; drop local PointTool wiring.

### ETDRS panel

- Keep grid overlay, selection, eye toggles, automatic keypoints.
- Open/edit → MultiFieldAdapter, `host: viewerContext`, slotKeys `f`/`d`.
- Item UI reflects `activeSlot`; landmark buttons set active slot (or re-arm with that slot) instead of swapping tools.

---

## 5. Edge cases

| Case | Behavior |
|------|----------|
| Re-arm same key | Toggle disarm |
| Arm different key | Replace previous session |
| Panel close / annotation removed | Disarm that key |
| Form then panel (or reverse) | Last arm wins — one global session |
| Read-only | `canEdit: false`; paint only |
| MultiField clear slot | `null` in list → clear/omit that field in form_data |
| Host viewer gone | Disarm on panel teardown; orphan session should not linger |

---

## 6. Testing

- **Unit — FieldAdapter:** bare single and byPublicId list round-trips (reuse schema helpers).
- **Unit — MultiFieldAdapter:** get/set ↔ `{ fovea, disc_edge }`; place/delete active slot.
- **Keep:** existing `pointSchema` / `pointMutations` tests (shapes unchanged).
- **Rewrite/drop:** tests or assumptions about dual tools / sibling hits / `isPlacementTarget`.
- **Manual:** Form Activate across multiple MainViewers; ETDRS both landmarks + `f`/`d` + grid sync; Registration nulls + digit focus.

---

## Success criteria

- Single arming API; at most one point session; one `PointTool` per mounted viewer for that session.
- ETDRS dual-landmark UX preserved without two tools.
- FormData shapes unchanged; no server migration.
- ETDRS and Registration panels do not construct `PointTool`.
- `PointTool` no longer exposes host/sibling/placement-target options.
