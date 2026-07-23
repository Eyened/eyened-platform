# Enface Projection — Code Review & Refactor Design

**Date:** 2026-07-23  
**Status:** Draft — pending review  
**Branch:** `feature/enface-projection`  
**Scope:** Refactor / compactness pass on the enface projection feature (~1,350 lines added across 7 commits)

---

## Summary

The feature works: B-scan edits incrementally update per-layer R8 thickness textures; the top-row `_proj` viewer renders them in mask or heatmap mode with MC/ML layer visibility and opacity mirroring B-scan shaders.

The code is readable but has accumulated duplication, dead paths, doc drift, and a few layering issues introduced during the MC/ML extension. This document records a code scan and proposes a phased refactor to make the implementation more compact and better structured **without changing behavior**, except where noted as *logic-change candidates* that need explicit approval.

---

## Code Scan — File-by-File Observations

### `client/src/lib/webgl/enfaceProjection.ts` (273 lines)

**Role:** GPU projection engine — owns R8 `TextureData`, framebuffer, slice/all projection, CPU max-thickness cache.

| Observation | Severity | Notes |
|-------------|----------|-------|
| Dead export `projectSegmentationStates()` | Low | Only caller would be external batch helper; nothing imports it. |
| Thin wrappers `projectSlice()` / `projectAll()` | Low | Only used by dead export; manager calls `projectSliceForFeature` / `projectAllLayers` directly. |
| Duplicate `syncMaskToGpu()` | Low | Called at start of `projectSliceForFeature` and again inside each `get*MaskTexture` helper. |
| Three mask getter helpers | Medium | `getBinaryMaskSource`, `getProbabilityMaskTexture`, `getMultiMaskTexture` share the same sync-then-extract pattern; could be one `prepareMaskForProjection(mask, rep)` dispatch. |
| `attachFramebuffer()` every slice | Low | Re-binds FBO on every `projectSliceForFeature` / `clearSlice`; could bind once in constructor (framebuffer attachment is static). |
| `clearSlice` uses raw GL | Low | Inconsistent with projection paths that use shader passes; works but adds a second clearing mechanism alongside `clearAll()` → `textureData.clearData()`. |
| Cross-layer import | Medium | WebGL module imports `SIMPLE_ENFACE_FEATURE_INDEX` from `viewer-window/enfaceProjectionKeys.ts` — inverted dependency (GPU ← UI layer). |
| CPU `getMaxThickness()` | Info | Full texture readback on every heatmap repaint per visible layer. Acceptable for now; GPU reduction deferred by user choice. |

### `client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts` (247 lines)

**Role:** Lifecycle coordinator — attach segmentations, hook slice changes, expose visible projections for overlay.

| Observation | Severity | Notes |
|-------------|----------|-------|
| Unused `projImage` constructor arg | Low | Stored as `readonly projImage` but never read. Safe to remove from constructor + call site. |
| `getSegmentationKey()` called repeatedly | Low | `ensureAttached`, `attachSegmentationItem`, `getProjection` each recompute the same key. Minor noise. |
| Duplicated segmentation iteration | Medium | Same `visibleGrader + visibleModel` loop pattern as `MainViewerContext.repaint`; attach uses `grader + model` (all projectable, not just visible). Intentional but could share a small iterator helper. |
| `getEnfaceLayerColor()` in manager | Low | Color resolution is presentation concern; fits better next to visibility helpers in `enfaceProjectionKeys.ts` or a thin `enfaceProjectionVisibility.ts`. |
| Async `projectAllWhenReady` fire-and-forget | Info | Correct pattern; error only logged. No cancellation if item detached before ready resolves (guarded by `attachedItems.has`). |

### `client/src/lib/viewer-window/enfaceProjectionKeys.ts` (155 lines)

**Role:** Layer keys, projectability, MC/ML visibility, alpha, color helpers.

| Observation | Severity | Notes |
|-------------|----------|-------|
| Mixed responsibilities | Medium | Keys, eligibility, visibility, alpha mirroring, and color in one file. Works, but name suggests only keys. |
| `getActiveFeatureMask()` exported | Low | Used only by `getEnfaceLayerAlpha`; could be private unless needed elsewhere. |
| `getSubfeatureBit()` mirrors mask/B-scan logic | Info | Same `1 << (featureIndex - 1)` pattern as `MultiLabelMask`, `segmentationContext.isFeatureLayerVisible`. Centralizing subfeature bit math would reduce drift risk. |
| MC highlight condition | Info | Matches `fs_render_multi_class`: `highlighted \|\| activeMask === featureIndex`. ✓ |
| ML alpha | Info | Matches per-layer branch in `fs_render_multi_label` (0.1 inactive, 1.0 active/highlight, drawing suppresses). ✓ Compositing model differs — see *Logic-change candidates*. |

### `client/src/lib/viewer/overlays/EnfaceProjectionOverlay.ts` (47 lines)

**Role:** Render pass — iterate visible projections, set uniforms, call `renderEnfaceProjection` shader.

| Observation | Severity | Notes |
|-------------|----------|-------|
| Clean and minimal | — | Good reference for target complexity. |
| Per-layer heatmap max | Info | Each projection passes its own `getMaxThickness()`. Original design spec said global max across visible projections — behavior changed intentionally? |
| `color ?? colors[0]` fallback | Low | Defensive; `getEnfaceLayerColor` already returns a color. Redundant. |

### GPU shaders

| File | Observation |
|------|-------------|
| `fs_enface_project_mask.frag` | Unused `u_volume` uniform (legacy from volume-based prototype). |
| `fs_enface_project_probability.frag` | Clean; same loop structure as MC/ML. |
| `fs_enface_project_multiclass.frag` | Nearly identical to multilabel except `int(val) == u_feature_index` vs bitmask test. |
| `fs_enface_project_multilabel.frag` | Same loop; good candidate for shared GLSL snippet or code-gen. |
| `fs_render_enface_projection.frag` | `heatmap()` duplicates `fs_render_layers_enface.frag` palette. Could `#include` or extract shared chunk. |

### Integration & UI

| File | Observation |
|------|-------------|
| `TopViewer.svelte` | Mode labels/colors/icon wiring is clear. `projectionModeLabels` / `projectionModeHoverColors` could live beside `EnfaceProjectionMode` type in `viewer-utils.ts`. |
| `viewerWindowContext.svelte.ts` | Sets default `enfaceProjectionMode = "binary"` for `_proj` viewers; original design said default **Off**. |
| `MainViewer.svelte` | Minimal, correct: registers manager with `MainViewerContext`. |
| `shaders.ts` | Straightforward registration; 5 enface-related programs (+ legacy `enfaceProjection` for OCT enface image generation in `image3D.ts`). |

### Dead / legacy code

| Location | Lines | Issue |
|----------|-------|-------|
| `segmentationItem.svelte.ts` → `createEnfaceMask()` | ~90 | Marked `//TODO: finish`; duplicates projection logic with wrong row indexing (`bottom: i` vs `scanNr`), R32F, binary-only. Superseded by `EnfaceProjectionManager`. **Remove.** |
| `enfaceProjection.ts` → `projectSegmentationStates` | ~8 | Unused export. **Remove.** |
| `enfaceProjection.ts` → `projectSlice` / `projectAll` | ~20 | Unused wrappers if export removed. **Remove or keep as minimal public API** — prefer remove unless external API needed. |

### Documentation drift

| Document | Issue |
|----------|-------|
| `docs/superpowers/specs/2026-07-21-enface-projection-design.md` | Still describes R32F, single projection per segmentation, no MC/ML, default Off, global heatmap max. Needs addendum or supersession note. |
| `docs/superpowers/plans/2026-07-21-enface-projection-multiclass-multilabel.md` | Untracked; visibility rules in plan (activeIndices-only) differ from shipped behavior (eye toggle + B-scan alpha). |

---

## Architecture Diagram (current)

```
SegmentationItem.onSliceChanged(scanNr)
        │
        ▼
EnfaceProjectionManager.onSliceChanged
        │  for each featureIndex
        ▼
EnfaceProjection.projectSliceForFeature  ──► R8 row in layer texture
        │
        ▼ (each repaint, mode ≠ off)
EnfaceProjectionOverlay.repaint
        │  getVisibleProjections() filters by eye + alpha
        ▼
renderEnfaceProjection shader (binary | heatmap per layer pass)
```

**Layer storage:** `Map<layerKey, EnfaceProjection>` where `layerKey = "${segmentationKey}#${featureIndex}"`.

**Visibility stack:** parent in `shownSegmentations` → MC/ML eye toggle → per-layer alpha (active/highlight) → `mainViewerContext.alpha`.

---

## Logic-Change Candidates (require approval)

These would simplify code or fix inconsistencies but **change behavior**. Do not implement without sign-off.

### 1. ML overlap compositing

**Current:** Each ML subfeature is a separate enface thickness overlay pass (order-dependent stacking).  
**B-scan:** Single pass with weighted RGB mix across co-occurring labels on one pixel.  
**Simplification option:** Render ML enface as one RGBA texture updated per slice (heavier GPU work, matches B-scan).  
**Lighter option:** Keep separate layers; document visual difference as acceptable.

### 2. Heatmap normalization scope

**Current:** Per-projection `getMaxThickness()` — each layer heatmap scales independently.  
**Original design:** Global max across all visible projections in the frame.  
**Trade-off:** Per-layer is simpler and already shipped; global max needs one pass or shared uniform computed in overlay.

### 3. MC/ML visibility model

**MC/ML plan (uncommitted):** Show only layers matching `activeIndices` when segmentation is active.  
**Shipped:** Eye toggle (`visibleFeatureMask`) + inactive alpha (like B-scan). More code in `enfaceProjectionKeys.ts`.  
**Simplification option:** Revert to activeIndices-only filtering — less alpha logic, different UX.

### 4. Default projection mode

**Shipped:** `"binary"` on `_proj` load.  
**Original design:** `"off"`.  
**One-line change** in `viewerWindowContext.svelte.ts` if Off is preferred.

### 5. Attach scope

**Current:** `attachExistingSegmentations` attaches all projectable segmentations (creates textures + hooks), not only visible ones.  
**Alternative:** Lazy attach on first visibility — fewer textures for hidden segmentations, slightly more complex attach path.

### 6. Single texture per segmentation (MC/ML)

**Current:** N `EnfaceProjection` instances × N GPU textures for N subfeatures.  
**Alternative:** One `TextureData` with depth = scan count and channel packing / texture array — fewer objects, more complex shaders and partial updates.

---

## Refactor Approaches

### Approach A — Minimal cleanup (recommended baseline)

**Goal:** ~150–200 lines removed, no behavior change.

- Delete `createEnfaceMask`, `projectSegmentationStates`, unused wrappers, `projImage` param.
- Consolidate mask prep in `enfaceProjection.ts` (single dispatch, one `syncMaskToGpu`).
- Bind framebuffer once in `EnfaceProjection` constructor.
- Move `SIMPLE_ENFACE_FEATURE_INDEX` to `enfaceProjection.ts` or `webgl/enfaceProjectionConstants.ts` (fix import direction).
- Trim redundant nullish coalescing in overlay.
- Remove unused `u_volume` from mask projection shader (or document if kept for uniform layout parity).

**Pros:** Low risk, fast, immediate compactness.  
**Cons:** Does not unify visibility with B-scan; shader duplication remains.

### Approach B — Consolidate visibility & presentation (recommended second pass)

**Goal:** Clearer module boundaries; shared subfeature math.

- Rename or split `enfaceProjectionKeys.ts` → `enfaceProjectionLayers.ts` (keys + projectability) + `enfaceProjectionVisibility.ts` (visible/alpha/color), **or** one file with clear section comments.
- Extract shared `subfeatureBit(index)` used by keys, masks, segmentationContext (small shared util in `webgl/` or `panelSegmentation/`).
- Extract `forEachVisibleEnfaceLayer(ctx, callback)` in manager to dedupe iteration.
- Share heatmap GLSL via include or copy-once comment linking to `fs_render_layers_enface.frag`.
- Optionally merge MC/ML projection shaders with a `uniform int u_mode` (class index vs bitmask) — one program, slightly trickier uniforms.

**Pros:** Better structure, less drift vs B-scan, moderate line reduction.  
**Cons:** Touch more files; shared util needs careful placement to avoid circular imports.

### Approach C — Structural redesign (defer unless needed)

**Goal:** Fewer textures / passes for MC/ML.

- Packed multi-layer projection texture per segmentation.
- Single overlay compositing pass matching B-scan ML mix.

**Pros:** Potentially better GPU memory and visual parity.  
**Cons:** Large rewrite, high regression risk, conflicts with incremental slice update model.

**Recommendation:** **A then B.** Skip C unless overlap compositing or memory becomes a problem.

---

## Proposed Refactor Design (phased)

### Phase 1 — Safe deletion & local dedup (no approval needed)

1. Remove `SegmentationItem.createEnfaceMask()` and any references.
2. Remove `projectSegmentationStates`, `projectSlice`, `projectAll` from public API.
3. Remove unused `projImage` from `EnfaceProjectionManager`.
4. Refactor mask helpers → single internal `projectSliceForFeature` dispatch table.
5. Call `attachFramebuffer()` only in constructor (and after any future texture reallocation).
6. Move `SIMPLE_ENFACE_FEATURE_INDEX` to webgl-side constants file.

**Verification:** Manual smoke test (draw, undo, toggle mode, MC/ML eye + radio/checkbox, hide segmentation). `npm run check` in `client/`.

### Phase 2 — Structure & shader tidy (no approval needed)

1. Reorganize keys/visibility module(s) with documented sections or split files.
2. Add `subfeatureBit()` shared helper; update keys + segmentationContext to use it.
3. Extract `collectVisibleEnfaceLayers(manager, ctx): VisibleEnfaceProjection[]` logic helper to shrink manager.
4. Deduplicate heatmap function in render shaders (include or shared `.glsl` chunk).
5. Consider merging MC/ML projection fragment shaders behind one uniform mode.

**Verification:** Same manual tests; optional visual screenshot compare before/after.

### Phase 3 — Approved logic changes only

Implement only the logic-change candidates the user selects (see section above).

### Phase 4 — Documentation

1. Update `2026-07-21-enface-projection-design.md` addendum: R8, per-layer textures, MC/ML, visibility model, default mode, heatmap scaling.
2. Commit or archive MC/ML plan with note that shipped visibility differs.

---

## Testing Checklist (post-refactor)

- [ ] Binary / DualBitMask / Probability: draw, undo, redo, enface row updates
- [ ] Heatmap mode: scaling looks correct per layer
- [ ] Hide segmentation in panel → disappears from enface
- [ ] MC: eye toggle, radio selection, inactive alpha
- [ ] ML: eye toggle, checkbox selection, highlight, drawing at 0.1 alpha
- [ ] Mode cycle off → binary → heatmap → off
- [ ] Multiple segmentations on same instance
- [ ] `npm run check` passes

---

## Open Questions

1. **Priority:** Compactness and structure first, or pursue visual parity with B-scan ML compositing?
2. **Default mode:** Keep `"binary"` or revert to `"off"`?
3. **Heatmap max:** Keep per-layer or switch to global max across visible layers?
4. **Phase 3:** Which logic-change candidates (if any) should be in scope?

---

## Self-Review

- [x] No TBD placeholders in refactor phases
- [x] Architecture matches scanned code
- [x] Logic-change candidates explicitly flagged for approval
- [x] Scope fits a single implementation plan (Phases 1–2 safe; Phase 3 optional)
- [x] Ambiguity: default mode and heatmap scope called out as decisions
