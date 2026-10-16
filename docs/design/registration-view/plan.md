# Registration view Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the registration panel into a launcher that opens a same-window editor for one eye, with landmark viewers and an automatic colour blend.

**Architecture:** Pure functions decide grouping, palette, and which layers draw. `ViewerWindowContext` keeps the normal viewers mounted and skips them while an editor session is set. A full-window layer mounts new `Viewer`s on the existing graphics context: one per checked image with the point tool armed, plus one blend viewer whose renderer warps overlays through the existing registration graph.

**Tech Stack:** Svelte 5 runes, Vitest, Testing Library, existing WebGL2 viewer, existing `PointTool` and registration graph.

## Global Constraints

- The image list is the images already open in this viewer window (the current top row), not every image for the patient.
- Images are grouped by patient and eye. A registration never mixes eyes. An image with no laterality is its own group for that patient and is never mixed with a known eye.
- **New** creates the annotation when the editor opens, not when it is selected. Patient and laterality come from the group. Study and image id come from the first checked image.
- The editor is a full-window layer in this same window. It reuses the existing graphics context. It does not open a browser popup.
- The normal viewers stay mounted underneath. While the editor is open they do not paint. Closing the editor resumes them with their state intact.
- The editor uses the existing `Viewer` component, the existing point tool, the loaded images, and the existing registration graph. It does not reuse the top row, the side panels, or the main viewer.
- Colours are assigned in top-row order to the images currently included: the fixed image plus every checked image. A missing registration path does not change which images are included or which colour they have.
- Palette: 1 untinted; 2 red, cyan; 3 red, green, blue; 4 adds cyan; 5 adds magenta; 6 adds yellow; 7 or more repeats that six-colour list. The two-image case is red and cyan, not the first two entries of the six-colour list.
- "First" means first in current top-row order among the images that are checked.
- The fixed image is always drawn. A checked image is drawn only when a path into the fixed image exists. An unchecked image is not drawn. A checked image with no path still receives a palette colour.
- The session is not written to the view-state URL.
- Opacity, invert, a manual colour, reset, and any blend mode other than additive colour are out of scope.
- Do not change point storage or the registration math.
- Run tests from `client/` with `npm run test -- <path>`.

---

## File structure

- Create `client/src/lib/viewer-window/panelRegistration/groupOpenImages.ts` — group open images and match annotations to an eye.
- Create `client/src/lib/viewer-window/panelRegistration/groupOpenImages.test.ts`
- Create `client/src/lib/viewer-window/panelRegistration/blendColours.ts` — palette.
- Create `client/src/lib/viewer-window/panelRegistration/blendColours.test.ts`
- Create `client/src/lib/viewer-window/panelRegistration/blendLayers.ts` — who is included, coloured, and drawn; switching the fixed image.
- Create `client/src/lib/viewer-window/panelRegistration/blendLayers.test.ts`
- Create `client/src/lib/registration/glslPathBetween.ts` — bake a multi-hop GLSL `mapping` from the registration graph.
- Create `client/src/lib/registration/glslPathBetween.test.ts`
- Create `client/src/lib/webgl/colorBlendFragment.ts` — fragment source for the additive blend.
- Create `client/src/lib/webgl/colorBlendFragment.test.ts`
- Create `client/src/lib/webgl/colorBlendRenderer.ts` — `ImageRenderer` that runs that shader.
- Create `client/src/lib/viewer-window/panelRegistration/registrationSession.ts` — session type.
- Create `client/src/lib/viewer-window/panelRegistration/bindRegistrationPointTool.ts` — arm `PointTool` on one viewer.
- Create `client/src/lib/viewer-window/panelRegistration/bindRegistrationPointTool.test.ts`
- Create `client/src/lib/viewer-window/panelRegistration/RegistrationEditor.svelte` — full-window layer.
- Create `client/src/lib/viewer-window/panelRegistration/RegistrationThumbnail.svelte`
- Create `client/src/lib/viewer-window/panelRegistration/RegistrationBlend.svelte`
- Modify `client/src/lib/viewer-window/viewerWindowContext.svelte.ts` — session, paint skip.
- Modify `client/src/lib/viewer-window/ViewerWindow.svelte` — mount the editor.
- Modify `client/src/lib/viewer-window/panelRegistration/PanelRegistration.svelte` — launcher.
- Modify `client/src/lib/viewer-window/panelRegistration/PanelRegistration.test.ts`
- Modify `client/src/lib/viewer-window/panelHelp/RegistrationPanelHelp.svelte`
- Delete `client/src/lib/viewer-window/panelRegistration/RegistrationItem.svelte` — the launcher does not list activatable rows.
- Test `client/src/lib/viewer-window/viewerWindowContext.paint.test.ts`

A hop `bakeHopGlsl` cannot bake (empty `glslMapping`, unknown item type) makes `glslPathBetween` return null. That overlay is not drawn. Do not add new registration bakers.

The blend samples `image.texture` and is correct for 2D images. A 3D image is still listed and can hold landmarks. It is not drawn in the blend, because a volume texture is not a 2D sample. It still counts toward the palette when it is included.

---

### Task 1: Group open images

**Files:**
- Create: `client/src/lib/viewer-window/panelRegistration/groupOpenImages.ts`
- Test: `client/src/lib/viewer-window/panelRegistration/groupOpenImages.test.ts`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `export type EyeLaterality = "L" | "R" | null`
  - `export type OpenImage = { imageId: string; instanceId: string; patientId: number; laterality: EyeLaterality; studyId: number | undefined }`
  - `export type EyeGroup = { patientId: number; laterality: EyeLaterality; images: OpenImage[] }`
  - `export function groupOpenImages(images: readonly OpenImage[]): EyeGroup[]`
  - `export function canOpenRegistration(checkedCount: number, annotationChoice: string | null): boolean`
  - `export function annotationMatchesEye(annotation: { form_schema_id: number; patient_id?: number | null; laterality?: EyeLaterality; image_id?: string | null }, schemaId: number, patientId: number, laterality: EyeLaterality, imageLaterality: (imageId: string) => EyeLaterality | undefined): boolean`

`annotationMatchesEye` is stricter than the old panel when one side has no laterality: missing laterality matches only the unset group, and a known eye matches only that eye. That is what "never mix eyes" requires.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import {
    annotationMatchesEye,
    canOpenRegistration,
    groupOpenImages,
    type OpenImage,
} from "./groupOpenImages";

const img = (patch: Partial<OpenImage> & Pick<OpenImage, "imageId">): OpenImage => ({
    instanceId: patch.imageId,
    patientId: 1,
    laterality: "R",
    studyId: 9,
    ...patch,
});

describe("groupOpenImages", () => {
    it("splits by patient and eye and keeps top-row order inside a group", () => {
        const groups = groupOpenImages([
            img({ imageId: "a", laterality: "L" }),
            img({ imageId: "b", patientId: 2, laterality: "R" }),
            img({ imageId: "c", laterality: "L" }),
            img({ imageId: "d", laterality: null }),
        ]);
        expect(groups.map((g) => [g.patientId, g.laterality, g.images.map((i) => i.imageId)])).toEqual([
            [1, "L", ["a", "c"]],
            [2, "R", ["b"]],
            [1, null, ["d"]],
        ]);
    });

    it("puts two images with no laterality in one unset group, not with a known eye", () => {
        const groups = groupOpenImages([
            img({ imageId: "a", laterality: null }),
            img({ imageId: "b", laterality: "R" }),
            img({ imageId: "c", laterality: null }),
        ]);
        const unset = groups.find((g) => g.laterality === null);
        expect(unset?.images.map((i) => i.imageId)).toEqual(["a", "c"]);
        expect(groups.find((g) => g.laterality === "R")?.images.map((i) => i.imageId)).toEqual(["b"]);
    });
});

describe("canOpenRegistration", () => {
    it("requires two checked images and a choice", () => {
        expect(canOpenRegistration(2, "new")).toBe(true);
        expect(canOpenRegistration(2, "21")).toBe(true);
        expect(canOpenRegistration(1, "new")).toBe(false);
        expect(canOpenRegistration(2, null)).toBe(false);
        expect(canOpenRegistration(2, "")).toBe(false);
    });
});

describe("annotationMatchesEye", () => {
    const base = { form_schema_id: 4, patient_id: 1, laterality: "R" as const, image_id: null };

    it("matches schema, patient, and eye", () => {
        expect(annotationMatchesEye(base, 4, 1, "R", () => undefined)).toBe(true);
        expect(annotationMatchesEye(base, 4, 1, "L", () => undefined)).toBe(false);
        expect(annotationMatchesEye(base, 9, 1, "R", () => undefined)).toBe(false);
        expect(annotationMatchesEye({ ...base, patient_id: 2 }, 4, 1, "R", () => undefined)).toBe(false);
    });

    it("uses the image laterality when the annotation has none", () => {
        expect(
            annotationMatchesEye(
                { ...base, laterality: null, image_id: "img" },
                4,
                1,
                "L",
                () => "L",
            ),
        ).toBe(true);
    });

    it("keeps an unset annotation out of a known eye", () => {
        expect(
            annotationMatchesEye({ ...base, laterality: null, image_id: null }, 4, 1, "R", () => undefined),
        ).toBe(false);
        expect(
            annotationMatchesEye({ ...base, laterality: null, image_id: null }, 4, 1, null, () => undefined),
        ).toBe(true);
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/groupOpenImages.test.ts`

Expected: FAIL, cannot find module `./groupOpenImages`.

- [ ] **Step 3: Write minimal implementation**

```ts
export type EyeLaterality = "L" | "R" | null;

export type OpenImage = {
    imageId: string;
    instanceId: string;
    patientId: number;
    laterality: EyeLaterality;
    studyId: number | undefined;
};

export type EyeGroup = {
    patientId: number;
    laterality: EyeLaterality;
    images: OpenImage[];
};

export function groupOpenImages(images: readonly OpenImage[]): EyeGroup[] {
    const groups: EyeGroup[] = [];
    for (const image of images) {
        let group = groups.find(
            (g) => g.patientId === image.patientId && g.laterality === image.laterality,
        );
        if (!group) {
            group = { patientId: image.patientId, laterality: image.laterality, images: [] };
            groups.push(group);
        }
        group.images.push(image);
    }
    return groups;
}

export function canOpenRegistration(checkedCount: number, annotationChoice: string | null): boolean {
    return checkedCount >= 2 && annotationChoice !== null && annotationChoice !== "";
}

export function annotationMatchesEye(
    annotation: {
        form_schema_id: number;
        patient_id?: number | null;
        laterality?: EyeLaterality;
        image_id?: string | null;
    },
    schemaId: number,
    patientId: number,
    laterality: EyeLaterality,
    imageLaterality: (imageId: string) => EyeLaterality | undefined,
): boolean {
    if (annotation.form_schema_id !== schemaId) return false;
    if (annotation.patient_id !== patientId) return false;
    const fromImage =
        annotation.image_id != null ? imageLaterality(annotation.image_id) : undefined;
    const formLaterality = annotation.laterality ?? fromImage ?? null;
    return formLaterality === laterality;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/groupOpenImages.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/panelRegistration/groupOpenImages.ts \
  client/src/lib/viewer-window/panelRegistration/groupOpenImages.test.ts
git commit -m "$(cat <<'EOF'
feat(viewer): group registration images by eye

EOF
)"
```

---

### Task 2: Blend palette

**Files:**
- Create: `client/src/lib/viewer-window/panelRegistration/blendColours.ts`
- Test: `client/src/lib/viewer-window/panelRegistration/blendColours.test.ts`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `export type Rgb = readonly [number, number, number]`
  - `export function blendColours(count: number): { untinted: boolean; colours: Rgb[] }`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { blendColours } from "./blendColours";

const red: [number, number, number] = [1, 0, 0];
const green: [number, number, number] = [0, 1, 0];
const blue: [number, number, number] = [0, 0, 1];
const cyan: [number, number, number] = [0, 1, 1];
const magenta: [number, number, number] = [1, 0, 1];
const yellow: [number, number, number] = [1, 1, 0];

describe("blendColours", () => {
    it("leaves a single image untinted", () => {
        expect(blendColours(1)).toEqual({ untinted: true, colours: [[1, 1, 1]] });
    });

    it("uses red and cyan for two images", () => {
        expect(blendColours(2).colours).toEqual([red, cyan]);
        expect(blendColours(2).untinted).toBe(false);
    });

    it("uses red, green, and blue for three images", () => {
        expect(blendColours(3).colours).toEqual([red, green, blue]);
    });

    it("continues cyan, magenta, yellow and then repeats", () => {
        expect(blendColours(4).colours).toEqual([red, green, blue, cyan]);
        expect(blendColours(6).colours).toEqual([red, green, blue, cyan, magenta, yellow]);
        expect(blendColours(7).colours[6]).toEqual(red);
    });

    it("returns no colours for an empty set", () => {
        expect(blendColours(0)).toEqual({ untinted: false, colours: [] });
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/blendColours.test.ts`

Expected: FAIL, cannot find module `./blendColours`.

- [ ] **Step 3: Write minimal implementation**

```ts
export type Rgb = readonly [number, number, number];

const CYCLE: readonly Rgb[] = [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
    [0, 1, 1],
    [1, 0, 1],
    [1, 1, 0],
];

export function blendColours(count: number): { untinted: boolean; colours: Rgb[] } {
    if (count <= 0) return { untinted: false, colours: [] };
    if (count === 1) return { untinted: true, colours: [[1, 1, 1]] };
    if (count === 2) return { untinted: false, colours: [[1, 0, 0], [0, 1, 1]] };
    const colours: Rgb[] = [];
    for (let i = 0; i < count; i++) colours.push(CYCLE[i % CYCLE.length]!);
    return { untinted: false, colours };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/blendColours.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/panelRegistration/blendColours.ts \
  client/src/lib/viewer-window/panelRegistration/blendColours.test.ts
git commit -m "$(cat <<'EOF'
feat(viewer): assign registration blend colours

EOF
)"
```

---

### Task 3: Blend membership

**Files:**
- Create: `client/src/lib/viewer-window/panelRegistration/blendLayers.ts`
- Test: `client/src/lib/viewer-window/panelRegistration/blendLayers.test.ts`

**Interfaces:**
- Consumes: `blendColours` from Task 2
- Produces:
  - `export type BlendLayer = { imageId: string; role: "fixed" | "overlay"; colour: Rgb; untinted: boolean; draw: boolean }`
  - `export function blendLayers(input: { orderedImageIds: readonly string[]; fixedImageId: string; overlayImageIds: readonly string[]; hasPath: (overlayId: string, fixedId: string) => boolean; canSample: (imageId: string) => boolean }): BlendLayer[]`
  - `export function selectFixedImage(state: { fixedImageId: string; overlayImageIds: readonly string[] }, nextFixedId: string): { fixedImageId: string; overlayImageIds: string[] }`

`orderedImageIds` is the editor's images in top-row order. Included images are the fixed image plus `overlayImageIds`, emitted in `orderedImageIds` order. `draw` is true for the fixed image when `canSample` is true, and for an overlay when `canSample` is true and `hasPath` is true. Colour assignment uses the included list, including layers that are not drawn.

`selectFixedImage` removes `nextFixedId` from the overlays and adds the previous fixed id, so the previous fixed image stays visible.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { blendLayers, selectFixedImage } from "./blendLayers";

const always = () => true;
const never = () => false;

describe("blendLayers", () => {
    it("draws the fixed image and a checked image that has a path", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b"],
            fixedImageId: "a",
            overlayImageIds: ["b"],
            hasPath: always,
            canSample: always,
        });
        expect(layers.map((l) => [l.imageId, l.role, l.draw, l.colour])).toEqual([
            ["a", "fixed", true, [1, 0, 0]],
            ["b", "overlay", true, [0, 1, 1]],
        ]);
    });

    it("keeps a colour for a checked image with no path and does not draw it", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b", "c"],
            fixedImageId: "a",
            overlayImageIds: ["b", "c"],
            hasPath: (id) => id === "c",
            canSample: always,
        });
        expect(layers.map((l) => [l.imageId, l.draw, l.colour])).toEqual([
            ["a", true, [1, 0, 0]],
            ["b", false, [0, 1, 0]],
            ["c", true, [0, 0, 1]],
        ]);
    });

    it("drops an unchecked image and reassigns colours", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b", "c"],
            fixedImageId: "a",
            overlayImageIds: ["c"],
            hasPath: always,
            canSample: always,
        });
        expect(layers.map((l) => l.imageId)).toEqual(["a", "c"]);
        expect(layers.map((l) => l.colour)).toEqual([
            [1, 0, 0],
            [0, 1, 1],
        ]);
    });

    it("leaves a lone fixed image untinted", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b"],
            fixedImageId: "a",
            overlayImageIds: [],
            hasPath: always,
            canSample: always,
        });
        expect(layers).toEqual([
            { imageId: "a", role: "fixed", colour: [1, 1, 1], untinted: true, draw: true },
        ]);
    });

    it("does not draw an image that cannot be sampled", () => {
        const layers = blendLayers({
            orderedImageIds: ["a", "b"],
            fixedImageId: "a",
            overlayImageIds: ["b"],
            hasPath: always,
            canSample: (id) => id === "a",
        });
        expect(layers.find((l) => l.imageId === "b")?.draw).toBe(false);
        expect(layers.find((l) => l.imageId === "b")?.colour).toEqual([0, 1, 1]);
    });

    it("does not draw a fixed image that cannot be sampled", () => {
        const layers = blendLayers({
            orderedImageIds: ["vol"],
            fixedImageId: "vol",
            overlayImageIds: [],
            hasPath: never,
            canSample: never,
        });
        expect(layers[0]?.draw).toBe(false);
    });
});

describe("selectFixedImage", () => {
    it("keeps the previous fixed image as a checked overlay", () => {
        expect(selectFixedImage({ fixedImageId: "a", overlayImageIds: ["b", "c"] }, "b")).toEqual({
            fixedImageId: "b",
            overlayImageIds: ["c", "a"],
        });
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/blendLayers.test.ts`

Expected: FAIL, cannot find module `./blendLayers`.

- [ ] **Step 3: Write minimal implementation**

```ts
import { blendColours, type Rgb } from "./blendColours";

export type BlendLayer = {
    imageId: string;
    role: "fixed" | "overlay";
    colour: Rgb;
    untinted: boolean;
    draw: boolean;
};

export function blendLayers(input: {
    orderedImageIds: readonly string[];
    fixedImageId: string;
    overlayImageIds: readonly string[];
    hasPath: (overlayId: string, fixedId: string) => boolean;
    canSample: (imageId: string) => boolean;
}): BlendLayer[] {
    const overlays = new Set(input.overlayImageIds);
    const included = input.orderedImageIds.filter(
        (id) => id === input.fixedImageId || overlays.has(id),
    );
    const palette = blendColours(included.length);
    return included.map((imageId, index) => {
        const role = imageId === input.fixedImageId ? "fixed" : "overlay";
        const sampled = input.canSample(imageId);
        const draw =
            role === "fixed"
                ? sampled
                : sampled && input.hasPath(imageId, input.fixedImageId);
        return {
            imageId,
            role,
            colour: palette.colours[index]!,
            untinted: palette.untinted,
            draw,
        };
    });
}

export function selectFixedImage(
    state: { fixedImageId: string; overlayImageIds: readonly string[] },
    nextFixedId: string,
): { fixedImageId: string; overlayImageIds: string[] } {
    const overlayImageIds = state.overlayImageIds.filter((id) => id !== nextFixedId);
    if (state.fixedImageId !== nextFixedId) overlayImageIds.push(state.fixedImageId);
    return { fixedImageId: nextFixedId, overlayImageIds };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/blendLayers.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/panelRegistration/blendLayers.ts \
  client/src/lib/viewer-window/panelRegistration/blendLayers.test.ts
git commit -m "$(cat <<'EOF'
feat(viewer): decide which registration layers draw

EOF
)"
```

---

### Task 4: Pause background viewers

**Files:**
- Modify: `client/src/lib/viewer-window/viewerWindowContext.svelte.ts`
- Create: `client/src/lib/viewer-window/panelRegistration/registrationSession.ts`
- Test: `client/src/lib/viewer-window/viewerWindowContext.paint.test.ts`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `export type RegistrationEditorSession = { imageIds: string[]; annotationId: number }`
  - On `ViewerWindowContext`: `registrationEditor: RegistrationEditorSession | null`, `openRegistrationEditor(session: RegistrationEditorSession): void`, `closeRegistrationEditor(): void`
  - `editorViewers: Set<ViewerContext> | null` (field used by `repaint` and `addViewer`)

While `editorViewers` is a `Set`, `repaint` paints only viewers in that set. Viewers added through `addViewer` after the set exists are inserted into it. `closeRegistrationEditor` sets both `registrationEditor` and `editorViewers` to null. Do not write the session into `viewState`.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it, vi } from "vitest";
import { ViewerWindowContext } from "./viewerWindowContext.svelte";

function contextWith(viewers: { repaint: ReturnType<typeof vi.fn> }[]) {
    const ctx = Object.create(ViewerWindowContext.prototype) as ViewerWindowContext & {
        viewers: Set<unknown>;
        editorViewers: Set<unknown> | null;
        webgl: { clear: ReturnType<typeof vi.fn>; canvas: { width: number; height: number } };
    };
    ctx.viewers = new Set(viewers);
    ctx.editorViewers = null;
    ctx.registrationEditor = null;
    ctx.webgl = { clear: vi.fn(), canvas: { width: 8, height: 8 } };
    return ctx;
}

describe("ViewerWindowContext registration editor paint", () => {
    it("paints only viewers added during the session, then resumes the others", () => {
        const background = { repaint: vi.fn() };
        const editorViewer = { repaint: vi.fn() };
        const ctx = contextWith([background]);

        ctx.openRegistrationEditor({ imageIds: ["a", "b"], annotationId: 21 });
        ctx.addViewer(editorViewer as never);

        ctx.repaint();
        expect(background.repaint).not.toHaveBeenCalled();
        expect(editorViewer.repaint).toHaveBeenCalledOnce();

        ctx.closeRegistrationEditor();
        ctx.repaint();
        expect(background.repaint).toHaveBeenCalledOnce();
        expect(ctx.registrationEditor).toBeNull();
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/viewer-window/viewerWindowContext.paint.test.ts`

Expected: FAIL, `openRegistrationEditor` is not a function.

- [ ] **Step 3: Write minimal implementation**

Add `client/src/lib/viewer-window/panelRegistration/registrationSession.ts`:

```ts
export type RegistrationEditorSession = {
    imageIds: string[];
    annotationId: number;
};
```

In `ViewerWindowContext`, import that type and add:

```ts
import type { RegistrationEditorSession } from "./panelRegistration/registrationSession";

public registrationEditor: RegistrationEditorSession | null = $state(null);
private editorViewers: Set<ViewerContext> | null = null;

openRegistrationEditor(session: RegistrationEditorSession) {
    this.editorViewers = new Set();
    this.registrationEditor = session;
}

closeRegistrationEditor() {
    this.registrationEditor = null;
    this.editorViewers = null;
}
```

Change `addViewer` so a viewer added while the editor is open joins `editorViewers`:

```ts
addViewer(viewer: ViewerContext) {
    this.viewers.add(viewer);
    this.editorViewers?.add(viewer);
    return () => {
        this.viewers.delete(viewer);
        this.editorViewers?.delete(viewer);
    };
}
```

Change `repaint` to skip background viewers:

```ts
repaint() {
    this.webgl.clear({
        left: 0,
        bottom: 0,
        width: this.webgl.canvas.width,
        height: this.webgl.canvas.height,
    });
    const paint = this.editorViewers
        ? [...this.viewers].filter((viewer) => this.editorViewers!.has(viewer))
        : [...this.viewers];
    for (const viewer of paint) viewer.repaint();
}
```

The test assigns `editorViewers` from outside the class. Keep the field name `editorViewers`. TypeScript `private` is erased, so the test's assignment works. Do not rename it.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/lib/viewer-window/viewerWindowContext.paint.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/viewerWindowContext.svelte.ts \
  client/src/lib/viewer-window/panelRegistration/registrationSession.ts \
  client/src/lib/viewer-window/viewerWindowContext.paint.test.ts
git commit -m "$(cat <<'EOF'
feat(viewer): pause background viewers while registration is open

EOF
)"
```

---

### Task 5: GLSL path between two images

**Files:**
- Create: `client/src/lib/registration/glslPathBetween.ts`
- Test: `client/src/lib/registration/glslPathBetween.test.ts`

**Interfaces:**
- Consumes: `Registration.getPath`, `Registration.getRegistrationItem`, `bakeHopGlsl`, `composeGlslPath`
- Produces: `export function glslPathBetween(registration: Registration, fromId: string, toId: string, sizeOf: (id: string) => [number, number] | undefined): string | null`

The returned string is a `mapping(uv)` function. `uv` is in `fromId` space and the result is in `toId` space. Return null when `getPath` is missing, any hop has no item, any size is missing, or `bakeHopGlsl` returns null. Do not add bakers.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { Matrix } from "$lib/matrix";
import { AffineRegistration } from "./affine";
import { Registration } from "./registration.svelte";
import { glslPathBetween } from "./glslPathBetween";

function registrationWith(item: AffineRegistration) {
    const registration = new Registration();
    registration.importRegistrationItems([item]);
    registration.recomputePathsNow();
    return registration;
}

describe("glslPathBetween", () => {
    it("bakes a direct affine into mapping()", () => {
        const item = new AffineRegistration("fixed", "moving", Matrix.identity);
        const registration = registrationWith(item);
        const glsl = glslPathBetween(registration, "fixed", "moving", () => [10, 20]);
        expect(glsl).not.toBeNull();
        expect(glsl).toContain("vec2 mapping(vec2 uv)");
        expect(glsl).not.toContain("u_size_primary");
    });

    it("returns null when no path exists", () => {
        const registration = new Registration();
        registration.recomputePathsNow();
        expect(glslPathBetween(registration, "a", "b", () => [1, 1])).toBeNull();
    });

    it("returns null when a node has no size", () => {
        const item = new AffineRegistration("fixed", "moving", Matrix.identity);
        const registration = registrationWith(item);
        expect(
            glslPathBetween(registration, "fixed", "moving", (id) =>
                id === "fixed" ? [10, 10] : undefined,
            ),
        ).toBeNull();
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/registration/glslPathBetween.test.ts`

Expected: FAIL, cannot find module `./glslPathBetween`.

- [ ] **Step 3: Write minimal implementation**

```ts
import { bakeHopGlsl } from "./enfaceToProj";
import { composeGlslPath } from "./composeGlslPath";
import type { Registration } from "./registration.svelte";

export function glslPathBetween(
    registration: Registration,
    fromId: string,
    toId: string,
    sizeOf: (id: string) => [number, number] | undefined,
): string | null {
    const path = registration.getPath(fromId, toId);
    if (!path || path.length < 2) return null;
    const hops: string[] = [];
    for (let i = 0; i < path.length - 1; i++) {
        const source = path[i]!;
        const target = path[i + 1]!;
        const item = registration.getRegistrationItem(source, target);
        const srcSize = sizeOf(source);
        const dstSize = sizeOf(target);
        if (!item || !srcSize || !dstSize) return null;
        const hop = bakeHopGlsl(item, srcSize, dstSize);
        if (!hop) return null;
        hops.push(hop);
    }
    return composeGlslPath(hops);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/lib/registration/glslPathBetween.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/registration/glslPathBetween.ts \
  client/src/lib/registration/glslPathBetween.test.ts
git commit -m "$(cat <<'EOF'
feat(viewer): bake a registration path into GLSL

EOF
)"
```

---

### Task 6: Colour blend shader

**Files:**
- Create: `client/src/lib/webgl/colorBlendFragment.ts`
- Create: `client/src/lib/webgl/colorBlendFragment.test.ts`
- Create: `client/src/lib/webgl/colorBlendRenderer.ts`

**Interfaces:**
- Consumes: `TextureShaderProgram`, `getBaseUniforms`, `ImageRenderer`, `RenderTarget`, `ViewerContext`
- Produces:
  - `export function colorBlendFragment(mappings: readonly string[]): string`
  - `export type ColorBlendLayer = { texture: WebGLTexture; width: number; height: number; colour: readonly [number, number, number]; untinted: boolean; mapping: string | null }`
  - `export class ColorBlendRenderer implements ImageRenderer` with `setLayers(layers: ColorBlendLayer[]): void` and `renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget): void`

`mappings` has one entry per overlay, in draw order. The fixed layer is always sampler `u_layer0` and is sampled at `v_uv`. Overlay `i` (starting at 0) is sampler `u_layer{i+1}` and is sampled at `mapping_i(v_uv)`. Each `mappings[i]` must declare `vec2 mapping(vec2 uv)`. The generator renames that function to `mapping_i` before pasting it. A layer with `untinted: true` is emitted as its RGB. Every other drawn layer adds `luminance * colour`. Then apply `u_window_level` the same way as `redblue.frag`.

`setLayers` rebuilds the shader only when the joined mapping strings change. `renderImage` clears nothing; `ViewerWindowContext.repaint` already cleared the canvas. It calls `shader.pass` with `u_layerN`, `u_colourN` (a `vec3`), and the base uniforms from `getBaseUniforms`.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { colorBlendFragment } from "./colorBlendFragment";

const hop = `vec2 mapping(vec2 uv) { return uv; }`;

describe("colorBlendFragment", () => {
    it("samples the fixed layer at v_uv and the overlay through mapping_0", () => {
        const source = colorBlendFragment([hop]);
        expect(source).toContain("uniform sampler2D u_layer0");
        expect(source).toContain("uniform sampler2D u_layer1");
        expect(source).toContain("texture(u_layer0, v_uv)");
        expect(source).toContain("vec2 mapping_0(vec2 uv)");
        expect(source).toContain("texture(u_layer1, mapping_0(v_uv))");
        expect(source).not.toContain("vec2 mapping(vec2 uv)");
    });

    it("emits an untinted fixed layer when there are no overlays", () => {
        const source = colorBlendFragment([]);
        expect(source).toContain("u_untinted0");
        expect(source).not.toContain("u_layer1");
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/webgl/colorBlendFragment.test.ts`

Expected: FAIL, cannot find module `./colorBlendFragment`.

- [ ] **Step 3: Write minimal implementation**

`client/src/lib/webgl/colorBlendFragment.ts`:

```ts
export function colorBlendFragment(mappings: readonly string[]): string {
    const renamed = mappings.map((mapping, index) =>
        mapping.replace(/vec2\s+mapping\s*\(/g, `vec2 mapping_${index}(`),
    );
    const samplers = [
        "uniform sampler2D u_layer0;",
        "uniform vec3 u_colour0;",
        "uniform float u_untinted0;",
        ...mappings.flatMap((_, index) => {
            const n = index + 1;
            return [
                `uniform sampler2D u_layer${n};`,
                `uniform vec3 u_colour${n};`,
                `uniform float u_untinted${n};`,
            ];
        }),
    ];
    const samples = [
        "vec3 rgb = vec3(0.0);",
        "vec3 sample0 = texture(u_layer0, v_uv).rgb;",
        "float luma0 = dot(sample0, vec3(0.299, 0.587, 0.114));",
        "rgb += mix(luma0 * u_colour0, sample0, u_untinted0);",
        ...mappings.map((_, index) => {
            const n = index + 1;
            return [
                `vec3 sample${n} = texture(u_layer${n}, mapping_${index}(v_uv)).rgb;`,
                `float luma${n} = dot(sample${n}, vec3(0.299, 0.587, 0.114));`,
                `rgb += mix(luma${n} * u_colour${n}, sample${n}, u_untinted${n});`,
            ].join("\n    ");
        }),
    ];
    return `#version 300 es
precision highp float;
uniform vec2 u_window_level;
in vec2 v_uv;
layout(location = 0) out vec4 color_out;
${samplers.join("\n")}
${renamed.join("\n")}
void main() {
    ${samples.join("\n    ")}
    color_out.rgb = (255.0 * rgb - u_window_level.x) / (u_window_level.y - u_window_level.x);
    color_out.a = 1.0;
}
`;
}
```

`client/src/lib/webgl/colorBlendRenderer.ts`:

```ts
import { TextureShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { RenderTarget } from "./types";
import type { WebGL } from "./webgl";
import { getBaseUniforms, type ImageRenderer } from "./imageRenderer";
import { colorBlendFragment } from "./colorBlendFragment";

export type ColorBlendLayer = {
    texture: WebGLTexture;
    width: number;
    height: number;
    colour: readonly [number, number, number];
    untinted: boolean;
    mapping: string | null;
};

export class ColorBlendRenderer implements ImageRenderer {
    private shader: TextureShaderProgram | null = null;
    private shaderKey = "";
    private layers: ColorBlendLayer[] = [];

    constructor(private readonly webgl: WebGL) {}

    setLayers(layers: ColorBlendLayer[]) {
        this.layers = layers;
        const mappings = layers.slice(1).map((layer) => layer.mapping ?? "");
        const key = mappings.join("\n---\n");
        if (key === this.shaderKey && this.shader) return;
        this.shaderKey = key;
        this.shader = new TextureShaderProgram(this.webgl, colorBlendFragment(mappings));
    }

    renderImage(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        if (!this.shader || this.layers.length === 0) return;
        const uniforms = getBaseUniforms(viewerContext);
        this.layers.forEach((layer, index) => {
            uniforms[`u_layer${index}`] = layer.texture;
            uniforms[`u_colour${index}`] = [...layer.colour];
            uniforms[`u_untinted${index}`] = layer.untinted ? 1 : 0;
        });
        this.shader.pass(renderTarget, uniforms);
    }
}
```

`TextureShaderProgram` takes the fragment source as its second argument, matching `MultiImageRenderer`. Pass every drawn layer, fixed first, and only drawn layers. The caller (Task 8) filters `blendLayers` with `layer.draw` before `setLayers`, and passes `mapping: null` for the fixed layer.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/lib/webgl/colorBlendFragment.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/webgl/colorBlendFragment.ts \
  client/src/lib/webgl/colorBlendFragment.test.ts \
  client/src/lib/webgl/colorBlendRenderer.ts
git commit -m "$(cat <<'EOF'
feat(viewer): add an additive colour blend renderer

EOF
)"
```

---

### Task 7: Registration launcher panel

**Files:**
- Modify: `client/src/lib/viewer-window/panelRegistration/PanelRegistration.svelte`
- Modify: `client/src/lib/viewer-window/panelRegistration/PanelRegistration.test.ts`
- Delete: `client/src/lib/viewer-window/panelRegistration/RegistrationItem.svelte`

**Interfaces:**
- Consumes: `groupOpenImages`, `canOpenRegistration`, `annotationMatchesEye`, `OpenImage`, `ViewerWindowContext.openRegistrationEditor`, `createFormAnnotation`
- Produces: the panel UI. Props stay `{ active: boolean; registrationSchema: FormSchemaGET }` so `resolvePanels` does not change. `active` is unused; reference it with `void active` so the prop stays in the contract.

Checkbox label is `image.imageId`. Choice value `"new"` or the annotation id as a string. Checked ids live in component state per group. **Open** calls `createFormAnnotation` only for `"new"`, then `openRegistrationEditor({ imageIds, annotationId })`. `imageIds` are the checked public ids in group order. Study and `image_id` on the create call come from the first checked image's `studyId` and `instanceId`. `laterality` is the group laterality, omitted when null. `sub_task_id` is `taskContext?.subTask?.id`.

Images come from `viewerWindowContext.topViewers` in map order. Map each `AbstractImage` to `OpenImage`: `imageId = image.image_id`, `instanceId = image.instance.id`, `patientId = image.instance.patient.id`, `laterality = image.instance.laterality ?? null`, `studyId = image.instance.study?.id`.

- [ ] **Step 1: Write the failing test**

Replace `PanelRegistration.test.ts` with:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import { formAnnotations } from "$lib/data/stores.svelte";
import type { FormSchemaGET } from "../../../types/openapi_types";

const openRegistrationEditor = vi.fn();

vi.mock("$lib/data", async () => {
    const stores = await import("$lib/data/stores.svelte");
    return {
        formAnnotations: stores.formAnnotations,
        instances: stores.instances,
        createFormAnnotation: vi.fn(),
        deleteFormAnnotation: vi.fn(),
        setFormAnnotationValue: vi.fn(),
    };
});

const { createFormAnnotation } = await import("$lib/data");
const { default: PanelRegistration } = await import("./PanelRegistration.svelte");

const schema = { id: 4, name: "Registration", schema: {} } as FormSchemaGET;

function image(imageId: string, laterality: "L" | "R" | null) {
    return {
        image_id: imageId,
        instance: {
            id: imageId,
            patient: { id: 100 },
            study: { id: 50 },
            laterality,
        },
    };
}

const rightA = image("imgA", "R");
const rightB = image("imgB", "R");
const left = image("imgL", "L");

const contexts = new Map<string, unknown>([
    ["viewerContext", { image: { instance: rightA.instance } }],
    ["taskContext", { task: { task_definition: { config: {} } }, subTask: { id: 7 } }],
    ["globalContext", { canEdit: () => true }],
    [
        "viewerWindowContext",
        {
            topViewers: new Map([
                [rightA, {}],
                [left, {}],
                [rightB, {}],
            ]),
            openRegistrationEditor,
        },
    ],
]);

describe("PanelRegistration", () => {
    beforeEach(() => {
        formAnnotations.clear();
        openRegistrationEditor.mockReset();
        vi.mocked(createFormAnnotation).mockReset();
        formAnnotations.set(21, {
            id: 21,
            form_schema_id: 4,
            patient_id: 100,
            laterality: "R",
            image_id: null,
            creator: { id: 5, name: "me" },
            form_data: {},
        } as never);
    });

    function renderPanel() {
        return render(PanelRegistration, {
            props: { active: true, registrationSchema: schema },
            context: contexts,
        } as never);
    }

    it("groups a known eye apart from the other eye", () => {
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        const leftGroup = screen.getByRole("group", { name: "Patient 100 L" });
        expect(right).toHaveTextContent("imgA");
        expect(right).toHaveTextContent("imgB");
        expect(leftGroup).toHaveTextContent("imgL");
        expect(right).not.toHaveTextContent("imgL");
    });

    it("opens an existing annotation without creating one", async () => {
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        const open = right.querySelector("button")!;
        expect(open).toBeDisabled();
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgA" }));
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgB" }));
        expect(open).toBeDisabled();
        await fireEvent.change(right.querySelector("select")!, { target: { value: "21" } });
        expect(open).toBeEnabled();
        await fireEvent.click(open);
        expect(createFormAnnotation).not.toHaveBeenCalled();
        expect(openRegistrationEditor).toHaveBeenCalledWith({
            imageIds: ["imgA", "imgB"],
            annotationId: 21,
        });
    });

    it("creates a new annotation only when Open is clicked", async () => {
        vi.mocked(createFormAnnotation).mockResolvedValue({ id: 22 });
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgB" }));
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgA" }));
        expect(createFormAnnotation).not.toHaveBeenCalled();
        await fireEvent.change(right.querySelector("select")!, { target: { value: "new" } });
        await fireEvent.click(right.querySelector("button")!);
        await waitFor(() => {
            expect(createFormAnnotation).toHaveBeenCalledWith(
                expect.objectContaining({
                    form_schema_id: 4,
                    patient_id: 100,
                    laterality: "R",
                    image_id: "imgA",
                    study_id: 50,
                    sub_task_id: 7,
                    form_data: {},
                }),
            );
        });
        expect(openRegistrationEditor).toHaveBeenCalledWith({
            imageIds: ["imgA", "imgB"],
            annotationId: 22,
        });
    });

    it("does not open the editor when create fails", async () => {
        vi.mocked(createFormAnnotation).mockRejectedValue(new Error("nope"));
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgA" }));
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgB" }));
        await fireEvent.change(right.querySelector("select")!, { target: { value: "new" } });
        await fireEvent.click(right.querySelector("button")!);
        await waitFor(() => expect(createFormAnnotation).toHaveBeenCalled());
        expect(openRegistrationEditor).not.toHaveBeenCalled();
    });
});
```

`imageIds` stay in top-row order inside the group. `imgA` is before `imgB` in the right-eye group even when `imgB` is checked first, because `left` sits between them in the map and the right-eye group collects `imgA` then `imgB`. The create call uses the first checked image in that group order, which is `imgA`.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/PanelRegistration.test.ts`

Expected: FAIL, the current panel still shows "Create new" and does not show the group legend.

- [ ] **Step 3: Rewrite the panel**

Delete `RegistrationItem.svelte`. Replace `PanelRegistration.svelte` with a launcher that:

- reads `viewerWindowContext`, `taskContext`, and `globalContext` from context
- derives `OpenImage[]` from `topViewers` keys
- derives groups with `groupOpenImages`
- for each group, filters `formAnnotations` with `annotationMatchesEye`, passing `(imageId) => instances.get(imageId)?.laterality ?? null`
- holds checked ids and the annotation choice per group in the parent, keyed by `` `${patientId}:${laterality ?? "unset"}` ``. Choice is `""` until the user picks. Do not add a second component for this.
- renders one `<fieldset>` per group whose accessible name is `Patient {patientId} {L|R|unset}`
- renders a checkbox per image inside `<label>{imageId}<input type="checkbox" /></label>` so the accessible name is the image id, a `<select>` with an empty placeholder, one `<option value="new">New</option>`, and one option per annotation labelled `{creator.name} [{id}]`
- disables the button unless `canOpenRegistration(checked.length, choice || null)`
- on click, if `choice === "new"`, `await createFormAnnotation(...)` inside try/catch; on throw, return without opening
- calls `viewerWindowContext.openRegistrationEditor({ imageIds: checkedInGroupOrder, annotationId })`

`checkedInGroupOrder` filters `group.images` to the checked set so order stays top-row order, not click order.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/PanelRegistration.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/panelRegistration/PanelRegistration.svelte \
  client/src/lib/viewer-window/panelRegistration/PanelRegistration.test.ts
git rm client/src/lib/viewer-window/panelRegistration/RegistrationItem.svelte
git commit -m "$(cat <<'EOF'
feat(viewer): launch registration from eye groups

EOF
)"
```

---

### Task 8: Editor layer

**Files:**
- Create: `client/src/lib/viewer-window/panelRegistration/bindRegistrationPointTool.ts`
- Create: `client/src/lib/viewer-window/panelRegistration/bindRegistrationPointTool.test.ts`
- Create: `client/src/lib/viewer-window/panelRegistration/RegistrationThumbnail.svelte`
- Create: `client/src/lib/viewer-window/panelRegistration/RegistrationBlend.svelte`
- Create: `client/src/lib/viewer-window/panelRegistration/RegistrationEditor.svelte`
- Modify: `client/src/lib/viewer-window/ViewerWindow.svelte`
- Modify: `client/src/lib/viewer-window/panelHelp/RegistrationPanelHelp.svelte`

**Interfaces:**
- Consumes: `RegistrationEditorSession`, `blendLayers`, `selectFixedImage`, `glslPathBetween`, `ColorBlendRenderer`, `Viewer`, `ViewerContext`, `PointTool`, `getPointsForImage`, `setPointsForImage`, `setFormAnnotationValue`, `analyzePointSchema`, `mergeClientConfig`
- Produces: `export function bindRegistrationPointTool(args: { viewerContext: ViewerContext; annotationId: number; schema: JSONSchema; canEdit: boolean; pointMarker: { style: PointMarkerStyle; radius: number; color: string } }): () => void`

`bindRegistrationPointTool` copies the analysis block from the current `PanelRegistration.registrationAnalysis` (force `x-eyened-widget: keypoint`, and if `coordinateSpace === "enface2d"` treat it as `"oct"`). It constructs `PointTool` with that analysis, `canEdit`, and the point marker. `onChange` and `onPersist` both write `setPointsForImage` into `formAnnotations`, and `onPersist` also calls `setFormAnnotationValue`. Initial `tool.points` comes from `getPointsForImage`. It `addOverlay`s the tool and returns a dispose function that destroys the tool and removes the overlay.

`RegistrationThumbnail` builds a new `ViewerContext` for the image (do not reuse `topViewers`), `setContext("viewerContext", ...)`, calls `bindRegistrationPointTool` in an effect, and renders `<Viewer showInfo={false} />`.

`RegistrationBlend` holds `fixedImageId` and `overlayImageIds`. Initial fixed id is `imageIds[0]`. Initial overlays are the rest of `imageIds`. The radio calls `selectFixedImage`. The blend `ViewerContext` is rebuilt when the fixed image changes, and its `imageRenderer` is set to a `ColorBlendRenderer`. Each frame the component's effect computes `blendLayers` where `hasPath` is `glslPathBetween(...) !== null` and `canSample` is `image.is2D`. `sizeOf` looks up `width` and `height` from `topViewers` keys by `image_id`. `setLayers` receives only `layer.draw` entries, fixed first, `mapping` null for the fixed layer and the `glslPathBetween` string for each drawn overlay. The mapping direction is from the fixed id to the overlay id.

`RegistrationEditor` is `position: fixed; inset: 0; z-index: 20; background: black`, with a **Close** button at the top right that calls `closeRegistrationEditor`. The top row is 20% height, one thumbnail per `session.imageIds` in that order. The blend fills the rest. On mount, focus the editor root so keys do not stay on a viewer underneath.

`ViewerWindow.svelte` renders `<RegistrationEditor />` when `viewerWindowContext.registrationEditor` is set, as a sibling after the normal layout, inside the same context provider.

Replace `RegistrationPanelHelp.svelte` body with this copy:

```svelte
<p class="intro">
    Open a registration editor for images of one eye that are already in this window.
</p>
<section>
    <h2>Workflow</h2>
    <ul>
        <li>Images are grouped by patient and eye. Check at least two images in one group.</li>
        <li>Choose an existing registration, or <strong>New</strong>.</li>
        <li>Click <strong>Open</strong>. The editor covers the window. Close returns to this viewer.</li>
        <li>
            Each image in the editor already has the point tool on. Place matching landmarks.
            Three pairs are enough for a transform. Spread them out.
        </li>
    </ul>
</section>
<section>
    <h2>Blend</h2>
    <ul>
        <li>The radio chooses the fixed image. Its pixels stay in place.</li>
        <li>Check another image to draw it on top, warped into the fixed image.</li>
        <li>Two images are red and cyan. Three are red, green, and blue.</li>
        <li>An image with no registration path yet is left out until the points define one.</li>
    </ul>
</section>
<section>
    <h2>Editing points</h2>
    <ul>
        <li>Left click on empty space to add a point.</li>
        <li><kbd>Ctrl</kbd>-click places another point on top of an existing marker.</li>
        <li>Left click a point, then drag to move it.</li>
        <li>Right click a point to remove it.</li>
        <li>Hold Shift while clicking to pan and zoom.</li>
    </ul>
</section>
```

- [ ] **Step 1: Write the failing point-tool test**

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { formAnnotations } from "$lib/data/stores.svelte";

const toolSpies = vi.hoisted(() => ({
    tools: [] as { points: { x: number; y: number }[]; opts: { onPersist: (points: unknown) => void; canEdit: boolean }; destroy: () => void }[],
}));

vi.mock("$lib/viewer/tools/PointTool.svelte", () => ({
    PointTool: vi.fn().mockImplementation(function (this: {
        points: unknown[];
        opts: unknown;
        destroy: () => void;
    }, opts: unknown) {
        this.points = [];
        this.opts = opts;
        this.destroy = () => {};
        toolSpies.tools.push(this as never);
    }),
}));

const { bindRegistrationPointTool } = await import("./bindRegistrationPointTool");
const { setFormAnnotationValue } = await import("$lib/data");

vi.mock("$lib/data", async () => {
    const stores = await import("$lib/data/stores.svelte");
    return {
        formAnnotations: stores.formAnnotations,
        setFormAnnotationValue: vi.fn(),
    };
});

const schema = {
    type: "object",
    additionalProperties: {
        type: "array",
        items: {
            oneOf: [
                {
                    type: "object",
                    properties: {
                        x: { type: "number" },
                        y: { type: "number" },
                        index: { type: ["number", "null"] },
                    },
                    required: ["x", "y"],
                },
                { type: "null" },
            ],
        },
    },
};

describe("bindRegistrationPointTool", () => {
    beforeEach(() => {
        toolSpies.tools.length = 0;
        formAnnotations.clear();
        formAnnotations.set(21, {
            id: 21,
            form_data: { img: [{ x: 1, y: 2 }] },
        } as never);
        vi.mocked(setFormAnnotationValue).mockReset();
    });

    it("loads points and persists edits", () => {
        const addOverlay = vi.fn(() => vi.fn());
        const dispose = bindRegistrationPointTool({
            viewerContext: {
                image: { image_id: "img", instance: { id: "img" } },
                addOverlay,
            } as never,
            annotationId: 21,
            schema: schema as never,
            canEdit: true,
            pointMarker: { style: "cross", radius: 4, color: "red" },
        });
        expect(addOverlay).toHaveBeenCalledOnce();
        const tool = toolSpies.tools[0]!;
        expect(tool.points).toEqual([{ x: 1, y: 2 }]);
        tool.opts.onPersist([{ x: 3, y: 4 }]);
        expect(setFormAnnotationValue).toHaveBeenCalledWith(
            21,
            expect.objectContaining({ img: [{ x: 3, y: 4 }] }),
        );
        dispose();
    });

    it("passes canEdit false through to the tool", () => {
        bindRegistrationPointTool({
            viewerContext: {
                image: { image_id: "img", instance: { id: "img" } },
                addOverlay: () => () => {},
            } as never,
            annotationId: 21,
            schema: schema as never,
            canEdit: false,
            pointMarker: { style: "cross", radius: 4, color: "red" },
        });
        expect(toolSpies.tools.at(-1)?.opts.canEdit).toBe(false);
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/bindRegistrationPointTool.test.ts`

Expected: FAIL, cannot find module `./bindRegistrationPointTool`.

- [ ] **Step 3: Implement the binder, the three components, the window mount, and the help text**

`bindRegistrationPointTool.ts`:

```ts
import { formAnnotations, setFormAnnotationValue } from "$lib/data";
import {
    analyzePointSchema,
    getPointsForImage,
    setPointsForImage,
} from "$lib/forms/pointSchema";
import type { JSONSchema } from "$lib/forms/schemaType";
import type { PointMarkerStyle } from "$lib/config/clientDefaults";
import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";

const REGISTRATION_POINTS: JSONSchema = {
    type: "array",
    items: {
        oneOf: [
            {
                type: "object",
                properties: {
                    x: { type: "number" },
                    y: { type: "number" },
                    index: { type: ["number", "null"] },
                },
                required: ["x", "y"],
            },
            { type: "null" },
        ],
    },
};

function registrationAnalysis(schema: JSONSchema) {
    const withMarker = (value: JSONSchema): JSONSchema => ({
        ...value,
        type: "object",
        "x-eyened-widget": "keypoint",
    });
    const analyzed =
        analyzePointSchema(withMarker(schema)) ??
        analyzePointSchema(withMarker({ additionalProperties: REGISTRATION_POINTS }));
    if (analyzed && analyzed.coordinateSpace === "enface2d") {
        return { ...analyzed, coordinateSpace: "oct" as const };
    }
    return analyzed;
}

export function bindRegistrationPointTool(args: {
    viewerContext: ViewerContext;
    annotationId: number;
    schema: JSONSchema;
    canEdit: boolean;
    pointMarker: { style: PointMarkerStyle; radius: number; color: string };
}): () => void {
    const analysis = registrationAnalysis(args.schema);
    if (!analysis) return () => {};
    const publicId = args.viewerContext.image.image_id;
    const annotationId = args.annotationId;
    const write = (points: ReturnType<typeof getPointsForImage>, persist: boolean) => {
        const existing = formAnnotations.get(annotationId);
        if (!existing) return;
        const next = setPointsForImage(existing.form_data, publicId, points, analysis);
        formAnnotations.set(annotationId, { ...existing, form_data: next });
        if (persist) setFormAnnotationValue(annotationId, next);
    };
    const tool = new PointTool({
        canEdit: args.canEdit,
        label: "registration",
        pointStyle: args.pointMarker.style,
        radius: args.pointMarker.radius,
        color: args.pointMarker.color,
        cardinality: analysis.cardinality,
        sparse: analysis.sparse,
        coordinateSpace: analysis.coordinateSpace,
        onChange: (points) => write(points, false),
        onPersist: (points) => write(points, true),
    });
    const existing = formAnnotations.get(annotationId)?.form_data;
    tool.points = getPointsForImage(existing, publicId, analysis);
    const removeOverlay = args.viewerContext.addOverlay(tool);
    return () => {
        tool.destroy();
        removeOverlay();
    };
}
```

Public id is `image.image_id`, so a `_proj` image stores points under that key.

`RegistrationEditor` returns immediately if `viewerWindowContext.registrationEditor` is null. Resolve images by walking `topViewers` keys and picking those whose `image_id` is in `session.imageIds`, in session order. If any session id is missing from `topViewers`, call `closeRegistrationEditor()` and render nothing, so a failed open does not leave the background viewers paused.

The editor looks up the pointset schema with `formSchemas.find` on `BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION`, the same lookup `MainViewer` uses. The point marker comes from `mergeClientConfig(CLIENT_DEFAULTS, taskContext?.task.task_definition.config).point_marker`. `canEdit` is `globalContext.canEdit(formAnnotations.get(session.annotationId))`.

`RegistrationBlend` controls sit in a column on the right of the blend viewer: one radio per session image, and a checkbox for every image that is not the current fixed image. Checkbox checked state is `overlayImageIds.includes(id)`.

Wire `ViewerWindow.svelte`:

```svelte
{#if viewerWindowContext.registrationEditor}
    <RegistrationEditor />
{/if}
```

Place it inside the `viewerWindowContext` context, after the `#main` grid, so the fixed layer covers that grid.

- [ ] **Step 4: Run the tests**

Run: `npm run test -- src/lib/viewer-window/panelRegistration/bindRegistrationPointTool.test.ts src/lib/viewer-window/panelRegistration/PanelRegistration.test.ts src/lib/webgl/colorBlendFragment.test.ts src/lib/registration/glslPathBetween.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/lib/viewer-window/panelRegistration/bindRegistrationPointTool.ts \
  client/src/lib/viewer-window/panelRegistration/bindRegistrationPointTool.test.ts \
  client/src/lib/viewer-window/panelRegistration/RegistrationThumbnail.svelte \
  client/src/lib/viewer-window/panelRegistration/RegistrationBlend.svelte \
  client/src/lib/viewer-window/panelRegistration/RegistrationEditor.svelte \
  client/src/lib/viewer-window/ViewerWindow.svelte \
  client/src/lib/viewer-window/panelHelp/RegistrationPanelHelp.svelte
git commit -m "$(cat <<'EOF'
feat(viewer): open a registration editor over the current viewers

EOF
)"
```

---

## Spec coverage

- Eye groups, unset laterality, two-image minimum, existing or new annotation: Task 1 and Task 7.
- New annotation created on open, failed create leaves the editor closed: Task 7.
- Full-window layer, close, background viewers stay mounted and resume: Task 4 and Task 8.
- Reuse `Viewer`, point tool, images, registration graph: Task 8.
- Palette, including reassignment when an image is hidden: Task 2 and Task 3.
- Fixed radio, overlay checkboxes, previous fixed stays checked: Task 3 and Task 8.
- Missing path is not drawn and still has a colour: Task 3 and Task 5.
- 3D images are not sampled in the blend: Task 3 `canSample` and Task 8.
- Points read and write through the existing annotation path, including read-only: Task 8.
- Help text: Task 8.
- Session is not stored in the view-state URL: Task 4 (`openRegistrationEditor` only sets fields).

## Out of scope reminder

Do not add opacity, invert, a colour picker, reset, another blend mode, a popup window, or changes to point storage or registration math.
