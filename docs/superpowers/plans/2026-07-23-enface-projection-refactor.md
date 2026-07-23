# Enface Projection Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compact and restructure the enface projection code (Phases 1–2 from the refactor design) with **zero behavior change**.

**Architecture:** Remove dead code and local duplication in the WebGL projection layer, fix the inverted constant import, then split visibility/presentation helpers out of the manager and deduplicate GLSL. No logic-change candidates (ML compositing, heatmap scope, default mode, lazy attach) are in scope.

**Tech stack:** SvelteKit 5, Svelte 5 runes, WebGL2, Vite raw GLSL imports (`?raw`).

**Spec:** `docs/superpowers/specs/2026-07-23-enface-projection-refactor-design.md`

## Global Constraints

- **Zero behavior change** — no logic-change candidates from the spec.
- Client-side only; no API or server changes.
- Preserve existing enface projection UX: mode cycle, MC/ML eye toggle + inactive alpha, per-layer heatmap scaling.
- Manual smoke test after each task; `npm run check` in `client/` before every commit.
- Frequent commits — one commit per task.

---

## File map (before → after)

| File | Phase | Change |
|------|-------|--------|
| `client/src/lib/webgl/segmentationItem.svelte.ts` | 1 | Remove `createEnfaceMask()` (~90 lines) |
| `client/src/lib/webgl/enfaceProjection.ts` | 1 | Dedup mask dispatch, bind FBO once, move constant, remove dead exports |
| `client/src/lib/webgl/enfaceProjectionConstants.ts` | 1 | **Create** — `SIMPLE_ENFACE_FEATURE_INDEX` |
| `client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts` | 1–2 | Remove `projImage`; shrink via visibility helper |
| `client/src/lib/viewer-window/viewerWindowContext.svelte.ts` | 1 | Drop `projImage` arg from manager ctor |
| `client/src/lib/viewer-window/enfaceProjectionKeys.ts` | 2 | Slim to keys + projectability only |
| `client/src/lib/viewer-window/enfaceProjectionVisibility.ts` | 2 | **Create** — visibility, alpha, color, enumeration |
| `client/src/lib/viewer-window/panelSegmentation/subfeatureBits.ts` | 2 | **Create** — shared `subfeatureBit()` |
| `client/src/lib/viewer-window/panelSegmentation/segmentationContext.svelte.ts` | 2 | Use `subfeatureBit()` |
| `client/src/lib/viewer/overlays/EnfaceProjectionOverlay.ts` | 1 | Remove redundant `?? colors[0]` |
| `client/src/lib/webgl/glsl/fs_enface_project_mask.frag` | 1 | Remove unused `u_volume` |
| `client/src/lib/viewer/overlays/heatmap.inc.glsl` | 2 | **Create** — shared heatmap function |
| `client/src/lib/viewer/overlays/fs_render_enface_projection.frag` | 2 | Use heatmap include |
| `client/src/lib/viewer/overlays/fs_render_layers_enface.frag` | 2 | Use heatmap include |
| `client/src/lib/webgl/shaders.ts` | 2 | Inject heatmap include; optionally merge MC/ML programs |
| `client/src/lib/webgl/glsl/fs_enface_project_multifeature.frag` | 2 | **Create** (optional Task 6) — merged MC/ML projection shader |

---

### Task 1: Remove dead code

**Files:**
- Modify: `client/src/lib/webgl/segmentationItem.svelte.ts`
- Modify: `client/src/lib/webgl/enfaceProjection.ts`

**Interfaces:**
- Removes: `SegmentationItem.createEnfaceMask()`, `EnfaceProjection.projectSlice()`, `EnfaceProjection.projectAll()`, `projectSegmentationStates()`
- Unchanged public API: `projectSliceForFeature`, `projectAllLayers`, `clearSlice`, `clearAll`, `getMaxThickness`, `dispose`

- [ ] **Step 1:** Delete `createEnfaceMask()` from `segmentationItem.svelte.ts` (lines ~235–328). Confirm no callers:

```bash
cd client && rg 'createEnfaceMask' src/
```

Expected: no matches after deletion.

- [ ] **Step 2:** Delete from `enfaceProjection.ts`:
  - `projectSlice()` method
  - `projectAll()` method
  - `projectSegmentationStates()` export

- [ ] **Step 3:** Run typecheck:

```bash
cd client && npm run check
```

Expected: PASS (no references to removed symbols).

- [ ] **Step 4:** Commit

```bash
git add client/src/lib/webgl/segmentationItem.svelte.ts client/src/lib/webgl/enfaceProjection.ts
git commit -m "Remove dead enface projection code paths."
```

**Manual check:** Open OCT instance, draw on B-scan — enface still updates.

---

### Task 2: Move constant + remove unused `projImage`

**Files:**
- Create: `client/src/lib/webgl/enfaceProjectionConstants.ts`
- Modify: `client/src/lib/webgl/enfaceProjection.ts`
- Modify: `client/src/lib/viewer-window/enfaceProjectionKeys.ts`
- Modify: `client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts`
- Modify: `client/src/lib/viewer-window/viewerWindowContext.svelte.ts`

**Interfaces:**
- Produces: `SIMPLE_ENFACE_FEATURE_INDEX` in `enfaceProjectionConstants.ts` (re-exported from keys for existing importers)

- [ ] **Step 1:** Create `enfaceProjectionConstants.ts`:

```typescript
/** Feature index for Binary / DualBitMask / Probability (single-layer projection). */
export const SIMPLE_ENFACE_FEATURE_INDEX = 0;
```

- [ ] **Step 2:** In `enfaceProjectionKeys.ts`, replace local constant with re-export:

```typescript
export { SIMPLE_ENFACE_FEATURE_INDEX } from "$lib/webgl/enfaceProjectionConstants";
```

- [ ] **Step 3:** In `enfaceProjection.ts`, import from constants instead of keys:

```typescript
import { SIMPLE_ENFACE_FEATURE_INDEX } from "./enfaceProjectionConstants";
```

- [ ] **Step 4:** Remove `projImage` from `EnfaceProjectionManager`:

```typescript
// Before
constructor(readonly octImage: Image3D, readonly projImage: Image2D) {}

// After
constructor(readonly octImage: Image3D) {}
```

Remove unused `Image2D` import if no longer needed.

- [ ] **Step 5:** In `viewerWindowContext.svelte.ts`, update manager construction:

```typescript
new EnfaceProjectionManager(octImage as Image3D),
```

- [ ] **Step 6:** Run `npm run check` — expect PASS.

- [ ] **Step 7:** Commit

```bash
git add client/src/lib/webgl/enfaceProjectionConstants.ts \
  client/src/lib/webgl/enfaceProjection.ts \
  client/src/lib/viewer-window/enfaceProjectionKeys.ts \
  client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts \
  client/src/lib/viewer-window/viewerWindowContext.svelte.ts
git commit -m "Fix enface constant layering and drop unused projImage."
```

---

### Task 3: Consolidate mask dispatch + bind framebuffer once

**Files:**
- Modify: `client/src/lib/webgl/enfaceProjection.ts`
- Modify: `client/src/lib/webgl/glsl/fs_enface_project_mask.frag`
- Modify: `client/src/lib/viewer/overlays/EnfaceProjectionOverlay.ts`

**Interfaces:**
- Internal only: replaces `getBinaryMaskSource`, `getProbabilityMaskTexture`, `getMultiMaskTexture` with unified dispatch inside `projectSliceForFeature`

- [ ] **Step 1:** Refactor `enfaceProjection.ts` mask helpers into one internal function:

```typescript
type MaskProjectionUniforms =
    | { shader: "binary"; u_mask: WebGLTexture; u_mask_bitmask: number }
    | { shader: "probability"; u_mask: WebGLTexture }
    | { shader: "multiclass"; u_mask: WebGLTexture; u_feature_index: number }
    | { shader: "multilabel"; u_mask: WebGLTexture; u_feature_bitmask: number };

function getMaskProjectionUniforms(
    mask: Mask,
    featureIndex: number,
): MaskProjectionUniforms {
    syncMaskToGpu(mask);
    const rep = mask.segmentation.data_representation;

    if (rep === "Probability" && mask instanceof ProbabilityMask) {
        return { shader: "probability", u_mask: mask.textureData.texture };
    }
    if (
        (rep === "Binary" || rep === "DualBitMask") &&
        (mask instanceof BinaryMask || mask instanceof QuestionableMask)
    ) {
        return {
            shader: "binary",
            u_mask: mask.bitMaskTexture.texture,
            u_mask_bitmask: mask.bitMaskTexture.bitmask,
        };
    }
    if (
        (rep === "MultiClass" || rep === "MultiLabel") &&
        (mask instanceof MultiClassMask || mask instanceof MultiLabelMask)
    ) {
        const u_mask = mask.textureData.texture;
        if (rep === "MultiClass") {
            return { shader: "multiclass", u_mask, u_feature_index: featureIndex };
        }
        return {
            shader: "multilabel",
            u_mask,
            u_feature_bitmask: 1 << (featureIndex - 1),
        };
    }
    throw new Error(
        `Unsupported mask for enface projection: ${mask.constructor.name} / ${rep}`,
    );
}
```

- [ ] **Step 2:** Simplify `projectSliceForFeature` — remove leading `syncMaskToGpu(mask)` and `attachFramebuffer()` calls; use dispatch:

```typescript
projectSliceForFeature(scanNr, mask, featureIndex, bscanHeight): void {
    if (scanNr < 0 || scanNr >= this.depth) return;

    const renderTarget = lineRenderTarget(this.framebuffer, this.width, scanNr, this.gl);
    const invHeight = 1 / bscanHeight;
    const base = { height: bscanHeight, u_inv_height: invHeight };
    const uniforms = getMaskProjectionUniforms(mask, featureIndex);

    switch (uniforms.shader) {
        case "binary":
            this.shaders.enfaceProjectBinary.pass(renderTarget, { ...base, u_mask: uniforms.u_mask, u_mask_bitmask: uniforms.u_mask_bitmask });
            break;
        case "probability":
            this.shaders.enfaceProjectProbability.pass(renderTarget, { ...base, u_mask: uniforms.u_mask });
            break;
        case "multiclass":
            this.shaders.enfaceProjectMultiClass.pass(renderTarget, { ...base, u_mask: uniforms.u_mask, u_feature_index: uniforms.u_feature_index });
            break;
        case "multilabel":
            this.shaders.enfaceProjectMultiLabel.pass(renderTarget, { ...base, u_mask: uniforms.u_mask, u_feature_bitmask: uniforms.u_feature_bitmask });
            break;
    }

    this.textureData.markCPUDirty();
    this.invalidateMaxThickness();
}
```

- [ ] **Step 3:** Keep `attachFramebuffer()` only in constructor (already called via `this.attachFramebuffer()` at end of ctor). Remove any remaining calls from `projectSliceForFeature`. For `clearSlice`, bind `this.framebuffer` directly without re-attaching texture:

```typescript
clearSlice(scanNr: number): void {
    if (scanNr < 0 || scanNr >= this.depth) return;
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.framebuffer);
    // ... rest unchanged
}
```

- [ ] **Step 4:** Remove unused uniforms from `fs_enface_project_mask.frag`:

```glsl
// Delete these lines:
uniform sampler3D u_volume;
```

- [ ] **Step 5:** In `EnfaceProjectionOverlay.ts`, simplify loop:

```typescript
for (const { projection, color, layerAlpha } of projections) {
    viewerContext.image.webgl.shaders.renderEnfaceProjection.pass(renderTarget, {
        ...uniforms,
        u_thickness: projection.textureData.texture,
        u_color: color.map((c) => c / 255),
        // ...
    });
}
```

- [ ] **Step 6:** Run `npm run check` — expect PASS.

- [ ] **Step 7:** Commit

```bash
git add client/src/lib/webgl/enfaceProjection.ts \
  client/src/lib/webgl/glsl/fs_enface_project_mask.frag \
  client/src/lib/viewer/overlays/EnfaceProjectionOverlay.ts
git commit -m "Consolidate enface mask projection dispatch and trim shader uniforms."
```

**Manual check:** Draw binary + probability segmentations; verify enface rows update.

---

### Task 4: Shared `subfeatureBit()` helper

**Files:**
- Create: `client/src/lib/viewer-window/panelSegmentation/subfeatureBits.ts`
- Modify: `client/src/lib/viewer-window/enfaceProjectionKeys.ts` (will move to visibility file in Task 5 — update whichever file holds `getSubfeatureBit` at this step)
- Modify: `client/src/lib/viewer-window/panelSegmentation/segmentationContext.svelte.ts`

**Interfaces:**
- Produces: `export function subfeatureBit(featureIndex: number): number`

- [ ] **Step 1:** Create `subfeatureBits.ts`:

```typescript
/** Bit for a 1-based subfeature index (matches B-scan MC/ML shaders). */
export function subfeatureBit(featureIndex: number): number {
    return featureIndex > 0
        ? ((1 << (featureIndex - 1)) >>> 0)
        : (1 >>> 0);
}
```

- [ ] **Step 2:** In `enfaceProjectionKeys.ts`, delete private `getSubfeatureBit` and import `subfeatureBit` instead. Update `getActiveFeatureMask` and `getEnfaceLayerAlpha` call sites.

- [ ] **Step 3:** In `segmentationContext.svelte.ts`, update `isFeatureLayerVisible` and `toggleFeatureLayerVisibility`:

```typescript
import { subfeatureBit } from "./subfeatureBits";

isFeatureLayerVisible(segmentation, featureIndex): boolean {
    const bit = subfeatureBit(featureIndex);
    return (this.getVisibleFeatureMask(segmentation) & bit) !== 0;
}

toggleFeatureLayerVisibility(segmentation, featureIndex): void {
    const key = getSegmentationKey(segmentation);
    const cur = this.getVisibleFeatureMask(segmentation) >>> 0;
    const bit = subfeatureBit(featureIndex);
    this.visibleFeatureMaskBySegmentationKey.set(key, (cur ^ bit) >>> 0);
}
```

- [ ] **Step 4:** Run `npm run check` — expect PASS.

- [ ] **Step 5:** Commit

```bash
git add client/src/lib/viewer-window/panelSegmentation/subfeatureBits.ts \
  client/src/lib/viewer-window/enfaceProjectionKeys.ts \
  client/src/lib/viewer-window/panelSegmentation/segmentationContext.svelte.ts
git commit -m "Extract shared subfeatureBit helper for MC/ML layer toggles."
```

---

### Task 5: Split visibility module + shrink manager

**Files:**
- Create: `client/src/lib/viewer-window/enfaceProjectionVisibility.ts`
- Modify: `client/src/lib/viewer-window/enfaceProjectionKeys.ts`
- Modify: `client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts`

**Interfaces:**
- Produces:
  - `getEnfaceLayerColor(segmentation, mainViewerContext, featureIndex): Color`
  - `enumerateVisibleEnfaceLayers(ctx, mainViewerContext, attachedItems): EnfaceLayerCandidate[]`
- `EnfaceLayerCandidate`: `{ segmentation, segmentationItem, featureIndex, layerAlpha, color }`
- Consumes: keys helpers from `enfaceProjectionKeys.ts`, `EnfaceProjection` type for final mapping in manager

- [ ] **Step 1:** Create `enfaceProjectionVisibility.ts` — move from keys:
  - `getSubfeatureColor`
  - `getActiveFeatureMask` (make non-exported / private in this file)
  - `isEnfaceLayerVisible`
  - `getEnfaceLayerAlpha`
  - Add `getEnfaceLayerColor(segmentation, mainViewerContext, featureIndex)`
  - Add `enumerateVisibleEnfaceLayers(...)`

```typescript
export type EnfaceLayerCandidate = {
    segmentation: Segmentation;
    segmentationItem: SegmentationItem;
    featureIndex: number;
    layerAlpha: number;
    color: Color;
};

export function enumerateVisibleEnfaceLayers(
    ctx: SegmentationContext,
    mainViewerContext: MainViewerContext | undefined,
    attachedItems: ReadonlyMap<string, SegmentationItem>,
): EnfaceLayerCandidate[] {
    if (!mainViewerContext) return [];
    const result: EnfaceLayerCandidate[] = [];

    for (const segmentation of [
        ...ctx.visibleGraderSegmentations,
        ...ctx.visibleModelSegmentations,
    ]) {
        if (!isProjectable(segmentation)) continue;

        const segmentationKey = getSegmentationKey(segmentation);
        const segmentationItem = ctx.getSegmentationItem(segmentation);
        if (!attachedItems.has(segmentationKey)) continue;

        for (const featureIndex of getEnfaceFeatureIndices(segmentation)) {
            if (!isEnfaceLayerVisible(segmentation, featureIndex, ctx)) continue;

            const layerAlpha = getEnfaceLayerAlpha(
                segmentation,
                featureIndex,
                ctx,
                mainViewerContext.highlightedFeatureIndex,
            );
            if (layerAlpha <= 0) continue;

            result.push({
                segmentation,
                segmentationItem,
                featureIndex,
                layerAlpha,
                color: getEnfaceLayerColor(segmentation, mainViewerContext, featureIndex),
            });
        }
    }
    return result;
}
```

- [ ] **Step 2:** Slim `enfaceProjectionKeys.ts` to:
  - `SIMPLE_ENFACE_FEATURE_INDEX` re-export
  - `getEnfaceLayerKey`
  - `getSubfeatureIndices`
  - `isProjectable`
  - `getEnfaceFeatureIndices`
  - `isMultiFeatureEnfaceSegmentation`

- [ ] **Step 3:** Rewrite `getVisibleProjections()` in manager:

```typescript
getVisibleProjections(): VisibleEnfaceProjection[] {
    const ctx = this.mainViewerContext?.segmentationContext;
    if (!ctx) return [];

    return enumerateVisibleEnfaceLayers(ctx, this.mainViewerContext, this.attachedItems)
        .map(({ segmentation, segmentationItem, featureIndex, layerAlpha, color }) => {
            const layerKey = getEnfaceLayerKey(
                getSegmentationKey(segmentation),
                featureIndex,
            );
            const projection = this.projections.get(layerKey);
            if (!projection) return null;
            return {
                segmentation,
                segmentationItem,
                projection,
                featureIndex,
                color,
                layerAlpha,
            };
        })
        .filter((entry): entry is VisibleEnfaceProjection => entry !== null);
}
```

Keep `ensureAttached` call before enumeration OR call `ensureAttached` inside the loop in `enumerateVisibleEnfaceLayers` — **prefer keeping attach logic in manager**: call `ensureAttached` for each visible segmentation before `enumerateVisibleEnfaceLayers`, or pass an `ensureAttached(item)` callback. Simplest: in `getVisibleProjections`, first loop visible segmentations and `ensureAttached`, then enumerate.

```typescript
getVisibleProjections(): VisibleEnfaceProjection[] {
    const ctx = this.mainViewerContext?.segmentationContext;
    if (!ctx) return [];

    for (const segmentation of [
        ...ctx.visibleGraderSegmentations,
        ...ctx.visibleModelSegmentations,
    ]) {
        if (isProjectable(segmentation)) {
            this.ensureAttached(ctx.getSegmentationItem(segmentation));
        }
    }

    return enumerateVisibleEnfaceLayers(ctx, this.mainViewerContext, this.attachedItems)
        // ... map as above
}
```

- [ ] **Step 4:** Update imports across codebase — grep for moved symbols:

```bash
cd client && rg "getEnfaceLayerAlpha|getSubfeatureColor|isEnfaceLayerVisible" src/
```

Expected: only `enfaceProjectionVisibility.ts` and manager (via enumerate).

- [ ] **Step 5:** Run `npm run check` — expect PASS.

- [ ] **Step 6:** Commit

```bash
git add client/src/lib/viewer-window/enfaceProjectionVisibility.ts \
  client/src/lib/viewer-window/enfaceProjectionKeys.ts \
  client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts
git commit -m "Split enface visibility helpers and shrink projection manager."
```

**Manual check:** MC/ML eye toggles, radio/checkbox alpha, hide segmentation.

---

### Task 6: Shared heatmap GLSL include

**Files:**
- Create: `client/src/lib/viewer/overlays/heatmap.inc.glsl`
- Modify: `client/src/lib/viewer/overlays/fs_render_enface_projection.frag`
- Modify: `client/src/lib/viewer/overlays/fs_render_layers_enface.frag`
- Modify: `client/src/lib/webgl/shaders.ts`

**Interfaces:**
- Produces: `withHeatmap(fragmentSource: string)` injector (mirrors `withSegBoundsOutline`)

- [ ] **Step 1:** Create `heatmap.inc.glsl`:

```glsl
vec3 heatmap(float value) {
    const vec3 c1 = vec3(0.0, 0.0, 1.0);
    const vec3 c2 = vec3(0.0, 1.0, 0.0);
    const vec3 c3 = vec3(1.0, 1.0, 0.0);
    const vec3 c4 = vec3(1.0, 0.0, 0.0);

    if (value < 0.25) {
        return mix(c1, c2, value / 0.25);
    } else if (value < 0.5) {
        return mix(c2, c3, (value - 0.25) / 0.25);
    } else if (value < 0.75) {
        return mix(c3, c4, (value - 0.5) / 0.25);
    }
    return c4;
}
```

- [ ] **Step 2:** Remove local `heatmap()` from both fragment shaders.

- [ ] **Step 3:** In `shaders.ts`:

```typescript
import heatmapInc from "$lib/viewer/overlays/heatmap.inc.glsl?raw";

function withHeatmap(fragmentSource: string): string {
    return fragmentSource.replace(/^void main\(/m, `${heatmapInc}\nvoid main(`);
}
```

Apply to `renderEnfaceProjection` and `renderLayersEnface` program construction:

```typescript
this.renderEnfaceProjection = new TextureShaderProgram(
    webgl,
    withHeatmap(fs_renderEnfaceProjection),
);
this.renderLayersEnface = new TextureShaderProgram3D(
    webgl,
    withHeatmap(fs_render_layers_enface),
);
```

- [ ] **Step 4:** Run `npm run check` and quick manual heatmap toggle on enface.

- [ ] **Step 5:** Commit

```bash
git add client/src/lib/viewer/overlays/heatmap.inc.glsl \
  client/src/lib/viewer/overlays/fs_render_enface_projection.frag \
  client/src/lib/viewer/overlays/fs_render_layers_enface.frag \
  client/src/lib/webgl/shaders.ts
git commit -m "Share heatmap palette via GLSL include injection."
```

---

### Task 7 (optional): Merge MC/ML projection shaders

**Skip if time-constrained** — behavior-neutral but touches GPU program registration.

**Files:**
- Create: `client/src/lib/webgl/glsl/fs_enface_project_multifeature.frag`
- Modify: `client/src/lib/webgl/shaders.ts`
- Modify: `client/src/lib/webgl/enfaceProjection.ts`
- Delete: `fs_enface_project_multiclass.frag`, `fs_enface_project_multilabel.frag`

**Interfaces:**
- Replaces `enfaceProjectMultiClass` + `enfaceProjectMultiLabel` with single `enfaceProjectMultiFeature` program
- Uniform: `u_feature_mode` (`0` = class index equality, `1` = bitmask test), plus `u_feature_index` or `u_feature_bitmask`

- [ ] **Step 1:** Create merged shader with both branches behind `uniform int u_feature_mode`.

- [ ] **Step 2:** Register one program in `shaders.ts`; remove two old programs.

- [ ] **Step 3:** Update `projectSliceForFeature` multiclass/multilabel cases to use one shader with different uniforms.

- [ ] **Step 4:** Run `npm run check`; manual MC + ML draw test.

- [ ] **Step 5:** Commit

```bash
git commit -m "Merge MC/ML enface projection into one shader program."
```

---

### Task 8: Final verification

- [ ] **Step 1:** Run full client check:

```bash
cd client && npm run check
```

- [ ] **Step 2:** Manual smoke test (from spec):

| Check | Pass |
|-------|------|
| Binary draw / undo / redo → enface row | |
| Heatmap mode scaling | |
| Hide segmentation → gone from enface | |
| MC eye + radio + inactive alpha | |
| ML eye + checkbox + highlight + drawing alpha | |
| Mode cycle off → binary → heatmap → off | |
| Multiple segmentations same instance | |

- [ ] **Step 3:** Line-count sanity (optional):

```bash
git diff development --stat -- client/src/lib/webgl/enfaceProjection.ts \
  client/src/lib/viewer-window/enfaceProjectionManager.svelte.ts \
  client/src/lib/viewer-window/enfaceProjectionKeys.ts \
  client/src/lib/webgl/segmentationItem.svelte.ts
```

Target: net reduction ~150–200 lines vs pre-refactor branch tip.

---

## Out of scope (Phase 3+)

Do **not** implement unless user explicitly requests later:

- ML overlap compositing parity with B-scan
- Global heatmap max across visible layers
- activeIndices-only visibility model
- Default mode `"off"` instead of `"binary"`
- Lazy attach for hidden segmentations
- Packed multi-layer textures
- Design doc addendum (`2026-07-21-enface-projection-design.md`) — optional follow-up

---

## Plan self-review

| Spec item (Phase 1–2) | Task |
|-----------------------|------|
| Remove createEnfaceMask | Task 1 |
| Remove dead exports/wrappers | Task 1 |
| Remove projImage | Task 2 |
| Mask dispatch consolidation | Task 3 |
| attachFramebuffer once | Task 3 |
| Move SIMPLE_ENFACE_FEATURE_INDEX | Task 2 |
| Split keys/visibility | Task 5 |
| subfeatureBit shared | Task 4 |
| enumerateVisibleEnfaceLayers | Task 5 |
| Heatmap GLSL dedup | Task 6 |
| MC/ML shader merge (optional) | Task 7 |
| Overlay nullish trim | Task 3 |
| Remove u_volume uniform | Task 3 |

No placeholders. All logic-change candidates excluded per user choice **A**.
