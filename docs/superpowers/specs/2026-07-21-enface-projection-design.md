# B-scan → Enface Segmentation Projection — Design

**Date:** 2026-07-21  
**Status:** Approved  
**Branch:** `feature/enface-projection`  
**Issue:** [#128](https://github.com/Eyened/eyened-platform/issues/128) (step 1 only)  
**Scope:** Frontend — `client/` (SvelteKit 5, WebGL viewer)

## Context

OCT volumes load as a pair in the viewer: a synthetic enface image (`{instanceId}_proj`) in the top row and the 3D B-scan volume in the main viewer. Segmentations are drawn per B-scan slice (`sparse_axis=0`) and appear only on the active B-scan in the main viewer.

B-scans and the synthetic enface share a known registration (`OCTToProj` / `ProjToOCT` in `projectionRegistration.ts`): B-scan index `N` maps to enface row `y ≈ N`. Annotations on multiple B-scans can therefore be projected onto the enface as a thickness map.

A partial GPU implementation exists (`SegmentationItem.createEnfaceMask()`) but is incomplete — the projection shader is not registered and nothing calls it from the UI.

## Goals

- After every B-scan drawing interaction, incrementally update a client-side enface thickness texture for that segmentation.
- Display projected segmentations on the synthetic enface in the top row.
- Mirror visibility from the main viewer: only segmentations currently shown on the B-scan appear on the enface (no extra panel UI).
- Top-row toggle cycles **Off → Binary mask → Thickness heatmap → Off**.

## Non-goals

- Server persistence of the projection (no new segmentation rows, no API changes).
- Enface → B-scan or enface → enface reverse projection.
- Photo-locator IR instances (only synthetic `{id}_proj` from the same OCT volume).
- MultiClass, MultiLabel, and region segmentations (`image_projection_matrix != null`).

---

## Architecture

```
MainViewer (Image3D, axis=0)
  └── MainViewerContext
        └── SegmentationContext.shownSegmentations   ← visibility source of truth
        └── SegmentationItem (per B-scan segmentation)
              └── SegmentationState.draw/undo/redo ──► notifySliceChanged(scanNr)

ViewerWindowContext
  └── EnfaceProjectionManager (per OCT instance)
        └── Map<segmentationKey, EnfaceProjection>
              └── R32F TextureData (width × depth)
              └── projectSlice(scanNr)     ← GPU, one row per draw
              └── projectAll()             ← init / visibility / reload

TopViewer ({instanceId}_proj)
  └── EnfaceProjectionOverlay
        └── reads manager + mainViewerContext visibility
        └── render mode: off | binary | heatmap
  └── 3-state toggle button (top-row chrome)
```

### Persistence

Client-side only. Textures are recomputed from B-scan mask data on load. Nothing appears in the segmentation panel list.

### Projection math

For enface pixel `(x, scanLineY)` where `scanLineY` equals B-scan index:

| B-scan type | Per-column value |
|-------------|------------------|
| Binary | Count of foreground pixels along axial axis |
| DualBitMask | Count using draw bitmask only (bit 0) |
| Probability | Sum of float probability values along axial axis |

Output is stored as `R32F` regardless of source type (thickness / soft thickness).

### Visibility

The overlay reads `shownSegmentations` from the `MainViewerContext` on the paired OCT main viewer (same `instance.id`, `image.is3D`). No new show/hide controls.

---

## Components

### `EnfaceProjection` (`client/src/lib/webgl/enfaceProjection.ts`)

- Owns `TextureData` (`R32F`, `width × depth`) plus a dedicated framebuffer attached to that texture.
- `projectSlice(scanNr, mask)` — GPU projection into row `scanNr`.
- `projectAll(segmentationItem)` — project every loaded slice.
- `clearSlice(scanNr)` / `clearAll()`.
- `dispose()`.

### `EnfaceProjectionManager` (`client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts`)

- Created when an OCT instance loads with both `_proj` and 3D images.
- Holds `octImage`, `projImage`, and a map of `EnfaceProjection` keyed by segmentation key.
- Registers `onSliceChanged` on each eligible `SegmentationItem`.
- `registerMainViewerContext(ctx)` — called from `MainViewer` when OCT panel opens.
- `getVisibleProjections()` — filters by `shownSegmentations` and supported data types.

### `EnfaceProjectionOverlay` (`client/src/lib/viewer/overlays/EnfaceProjectionOverlay.ts`)

- Attached to the `_proj` top-row `ViewerContext`.
- Reads display mode from `ViewerContext.enfaceProjectionMode`.
- Renders visible projections using feature colors from the linked `MainViewerContext`.

### Update triggers

| Event | Action |
|-------|--------|
| `SegmentationState.draw()` | `projectSlice(scanNr)` |
| `undo()` / `redo()` | `projectSlice(scanNr)` |
| `importOther()` | `projectSlice(scanNr)` |
| Segmentation shown | `projectAll()` |
| Slice lazy-loaded | `projectSlice(scanNr)` |
| Manager init | `projectAll()` for visible segmentations |

Hook: `SegmentationItem.onSliceChanged?: (scanNr: number) => void`, invoked from `SegmentationState` after mask mutations (before debounced server save).

---

## GPU shaders

Register in `client/src/lib/webgl/shaders.ts`:

1. **`enfaceProjectBinary`** — adapt `fs_enface_project_mask.frag`: sum binary bitmask pixels along B-scan height.
2. **`enfaceProjectProbability`** — sum `sampler2D` float values along height.
3. **`renderEnfaceProjection`** — overlay shader with `u_mode` (`0` = binary, `1` = heatmap), `u_thickness` sampler, `u_color`, `u_max_thickness`, `u_alpha`. Heatmap uses blue→green→yellow→red (same as `fs_render_layers_enface.frag`).

---

## UI

On `_proj` top-row viewers only, a small icon button (same chrome as the OCT lines toggle) cycles:

**Off → Binary → Heatmap → Off**

- Default: **Off**
- State on `ViewerContext.enfaceProjectionMode`
- Only shown when the instance has a paired OCT volume

---

## Edge cases

- Empty slice → row cleared to 0.
- Heatmap normalizes by `max(thickness)` across visible projections in the current frame (minimum divisor 1).
- Undo/redo on any B-scan updates the correct enface row regardless of the currently viewed B-scan.
- Textures disposed when the viewer window unloads.

---

## Testing

Manual verification in the client:

1. Open an OCT instance; enable projection toggle on the enface thumbnail.
2. Draw on a B-scan → corresponding enface row updates live (binary and heatmap).
3. Hide a segmentation in the panel → it disappears from enface immediately.
4. Undo/redo → enface row reverts.
5. Draw on multiple B-scans → independent rows update.
