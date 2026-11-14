import { beforeEach, describe, expect, it, vi } from "vitest";
import { colors } from "$lib/viewer/overlays/colors";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import type { Image3D } from "$lib/webgl/image3D";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import type { Segmentation } from "./panelSegmentation/segmentationContext.svelte";

const { uploads } = vi.hoisted(() => ({ uploads: [] as Uint8Array[] }));

vi.mock("$lib/webgl/texture", () => ({
    TextureData: class {
        texture = {};
        uploadData(data: Uint8Array) {
            uploads.push(data);
        }
        dispose() {}
    },
}));

vi.mock("$lib/webgl/enfaceProjection", () => ({
    // Two en-face pixels: class 1 covers the first, class 2 both.
    EnfaceProjection: class {
        textureData = { texture: {}, data: Uint8Array.of(0, 0) };
        projectAllLayers(_item: unknown, featureIndex: number) {
            this.textureData.data =
                featureIndex === 1 ? Uint8Array.of(9, 0) : Uint8Array.of(9, 9);
        }
        clearSlice() {}
        dispose() {}
    },
}));

import { EnfaceProjectionManager } from "./enfaceProjectionManager.svelte";

const segmentation = {
    id: 1,
    annotation_type: "segmentation",
    data_representation: "MultiClass",
    feature: { subfeatures: [{ index: 1 }, { index: 2 }] },
} as unknown as Segmentation;

/** An OCT viewport showing one MultiClass segmentation with classes 1 and 2, class 2 active. */
function shownMultiClass() {
    const hidden = new Set<number>();
    const item = {
        segmentation,
        segmentationStates: new Map(),
    } as unknown as SegmentationItem;
    const ctx = {
        graderSegmentations: [segmentation],
        modelSegmentations: [],
        visibleGraderSegmentations: [segmentation],
        visibleModelSegmentations: [],
        activeIndices: 2 as number | number[],
        multiClassActiveAlpha: 1,
        multiClassInactiveAlpha: 0.2,
        isDrawing: false,
        getSegmentationItem: () => item,
        isFeatureLayerVisible: (_s: Segmentation, i: number) => !hidden.has(i),
    };
    const mainViewerContext = {
        segmentationContext: ctx,
    } as unknown as MainViewerContext;
    const manager = new EnfaceProjectionManager({
        webgl: { gl: {}, shaders: {} },
        width: 2,
        depth: 1,
        height: 4,
    } as unknown as Image3D);
    manager.registerMainViewerContext(mainViewerContext);
    // The manager keeps its context in $state, which proxies it: edit through the proxy.
    return {
        manager,
        ctx: manager.mainViewerContext!
            .segmentationContext as unknown as typeof ctx,
        hidden,
        item,
    };
}

beforeEach(() => {
    uploads.length = 0;
});

describe("EnfaceProjectionManager paint layers", () => {
    it("MultiClass Mask paints one class map, rebuilt only when a slice, the active class or the visible classes change", () => {
        const { manager, ctx, hidden, item } = shownMultiClass();
        expect(manager.getPaintLayers("binary")).toEqual([
            expect.objectContaining({ kind: "classMap", active: 2 }),
        ]);
        expect([...uploads[0]]).toEqual([2, 2]);
        ctx.multiClassInactiveAlpha = 0.5;
        manager.getPaintLayers("binary");
        expect(uploads).toHaveLength(1);
        hidden.add(2);
        manager.getPaintLayers("binary");
        expect([...uploads[1]]).toEqual([1, 0]);
        item.onSliceChanged?.(0);
        manager.getPaintLayers("binary");
        expect(uploads).toHaveLength(3);
    });

    it("MultiClass Thickness paints only the active class, and nothing while several are active", () => {
        const { manager, ctx } = shownMultiClass();
        expect(manager.getPaintLayers("heatmap")).toEqual([
            expect.objectContaining({ kind: "projection", color: colors[1] }),
        ]);
        ctx.activeIndices = [1, 2];
        expect(manager.getPaintLayers("heatmap")).toEqual([]);
    });
});
