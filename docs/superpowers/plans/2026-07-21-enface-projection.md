# B-scan → Enface Segmentation Projection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live client-side projection of B-scan segmentations onto the synthetic enface thumbnail, with a top-row toggle for off / binary / heatmap display.

**Architecture:** Incremental GPU slice projection into per-segmentation `R32F` textures, managed by `EnfaceProjectionManager`, rendered via `EnfaceProjectionOverlay` on `_proj` top-row viewers. Visibility mirrors the OCT main viewer's `shownSegmentations`.

**Tech stack:** SvelteKit 5, Svelte 5 runes, WebGL2, existing `TextureData` / `PixelShaderProgram` / `TextureShaderProgram` infrastructure.

## Global Constraints

- Client-side only — no server persistence, no API changes, no segmentation panel UI.
- Supported source types: Binary, DualBitMask (draw bit only), Probability.
- Target: synthetic `{instanceId}_proj` enface only.
- Visibility must mirror `MainViewerContext.segmentationContext.shownSegmentations`.
- Default projection display mode: Off.

---

### Task 1: GPU projection shaders + `EnfaceProjection` class

**Files:**
- Create: `client/src/lib/webgl/glsl/fs_enface_project_probability.frag`
- Create: `client/src/lib/webgl/enfaceProjection.ts`
- Modify: `client/src/lib/webgl/shaders.ts`
- Modify: `client/src/lib/webgl/glsl/fs_enface_project_mask.frag` (rename export usage only if needed)

**Interfaces:**
- Produces: `EnfaceProjection` with `projectSlice(scanNr, mask, bscanHeight)`, `projectAll(states)`, `texture: TextureData`, `dispose()`.

- [ ] **Step 1:** Register `enfaceProjectBinary` (existing mask frag) and `enfaceProjectProbability` in `Shaders`.
- [ ] **Step 2:** Implement `EnfaceProjection` with dedicated framebuffer, row-scissor writes at `bottom = scanNr`.
- [ ] **Step 3:** Verify TypeScript compiles (`npm run check` in `client/`).

**Client check:** No visible change yet — internal foundation only.

---

### Task 2: `EnfaceProjectionManager` + draw hooks

**Files:**
- Create: `client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts`
- Modify: `client/src/lib/webgl/segmentationItem.svelte.ts` — add `onSliceChanged` callback
- Modify: `client/src/lib/webgl/segmentationState.svelte.ts` — call `notifySliceChanged` after draw/undo/redo/import
- Modify: `client/src/lib/viewer-window/viewerWindowContext.svelte.ts` — create manager when OCT+proj load

**Interfaces:**
- Consumes: `EnfaceProjection` from Task 1
- Produces: `EnfaceProjectionManager.onSliceChanged(item, scanNr)`, `getVisibleProjections()`, `registerMainViewerContext(ctx)`

- [ ] **Step 1:** Add `onSliceChanged` to `SegmentationItem`; invoke from `SegmentationState` mask mutations.
- [ ] **Step 2:** Implement manager: map segmentations, wire callbacks, `projectAll` on show.
- [ ] **Step 3:** Instantiate manager in `viewerWindowContext.loadImage` when `[Image2D _proj, Image3D]`.

**Client check:** Still no visible change; projections update in GPU memory on draw (can add temporary debug if needed).

---

### Task 3: Render overlay + top-row toggle

**Files:**
- Create: `client/src/lib/viewer/overlays/fs_render_enface_projection.frag`
- Create: `client/src/lib/viewer/overlays/EnfaceProjectionOverlay.ts`
- Modify: `client/src/lib/webgl/shaders.ts` — register `renderEnfaceProjection`
- Modify: `client/src/lib/viewer/viewerContext.svelte.ts` — add `enfaceProjectionMode`
- Modify: `client/src/lib/viewer-window/TopViewer.svelte` — toggle UI + attach overlay
- Modify: `client/src/lib/viewer-window/MainViewer.svelte` — `registerMainViewerContext`

**Interfaces:**
- Consumes: `EnfaceProjectionManager.getVisibleProjections()`, `MainViewerContext.getFeatureColor`
- Produces: visible enface overlay; `ViewerContext.enfaceProjectionMode: 'off' | 'binary' | 'heatmap'`

- [ ] **Step 1:** Implement render shader (binary + heatmap modes).
- [ ] **Step 2:** Implement `EnfaceProjectionOverlay.repaint()`.
- [ ] **Step 3:** Add 3-state toggle to `TopViewer` for `_proj` images; wire overlay in `$effect`.
- [ ] **Step 4:** Register `MainViewerContext` from OCT `MainViewer`.

**Client check:** Draw on B-scan → toggle enface to Binary or Heatmap → projection visible on top-row enface. Hide segmentation in panel → disappears from enface.

---

### Task 4: Polish + lifecycle

**Files:**
- Modify: `client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts`
- Modify: `client/src/lib/viewer-window/viewerWindowContext.svelte.ts`

- [ ] **Step 1:** Dispose projections on viewer window destroy.
- [ ] **Step 2:** `projectAll` when segmentation becomes visible or slice loads from server.
- [ ] **Step 3:** Final manual test pass per spec.

**Client check:** Full workflow — multi-slice draw, undo/redo, visibility toggle, mode cycle, reload recomputes from B-scans.
