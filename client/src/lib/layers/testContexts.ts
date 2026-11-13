import {
    SegmentationContext,
    type Segmentation,
} from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { SyncState } from "$lib/webgl/segmentationState.svelte";
import { SvelteSet } from "svelte/reactivity";
import { fromStore, writable, type Writable } from "svelte/store";
import { vi } from "vitest";
import type {
    ModelSegmentationGET,
    SegmentationGET,
} from "../../types/openapi_types";

export const ME = 5;

/** A synthetic grader segmentation. */
export function graderSegmentation(
    id: number,
    creatorId: number,
    name: string,
    over: Partial<SegmentationGET> = {},
): SegmentationGET {
    return {
        id,
        image_id: "inst-1",
        annotation_type: "grader_segmentation",
        data_representation: "DualBitMask",
        sparse_axis: null,
        threshold: 0.5,
        reference_segmentation_id: null,
        creator: { id: creatorId, name: `Grader ${creatorId}` },
        feature: { id: 100 + id, name },
        tags: [],
        ...over,
    } as unknown as SegmentationGET;
}

/** A synthetic model segmentation. */
export function modelSegmentation(
    id: number,
    name: string,
): ModelSegmentationGET {
    return {
        id,
        image_id: "inst-1",
        annotation_type: "model_segmentation",
        data_representation: "Probability",
        sparse_axis: null,
        threshold: 0.5,
        creator: { id: 99, name: "Model" },
        feature: { id: 200 + id, name },
        tags: [],
    } as unknown as ModelSegmentationGET;
}

/** The contexts a Layers section reads, with one save-state store per segmentation id. */
export function layersContexts(
    instanceId = "inst-1",
    over: {
        resolution?: { x: number; y: number; z: number };
        is3D?: boolean;
        getMask?: (index: number) => unknown;
        /** Every slice state's initial load, and whether its slice has nothing. */
        slice?: { loaded?: Promise<void>; isEmptyForSlice?: boolean };
    } = {},
) {
    const sync = new Map<number, Writable<SyncState>>();
    const getMask = over.getMask ?? (() => undefined);
    const items = new Map<string, unknown>();
    const image = {
        width: 100,
        height: 100,
        is3D: over.is3D ?? false,
        is2D: !(over.is3D ?? false),
        resolution: over.resolution ?? { x: -1, y: -1, z: -1 },
        getOrCreateSegmentationItem(segmentation: Segmentation) {
            const key = `${segmentation.annotation_type}_${segmentation.id}`;
            if (!items.has(key)) {
                if (!sync.has(segmentation.id))
                    sync.set(segmentation.id, writable<SyncState>("synced"));
                const syncState = sync.get(segmentation.id)!;
                items.set(key, {
                    segmentation,
                    loading: false,
                    threshold: 0.5,
                    importOther: vi.fn(async () => {}),
                    savedScanIndices: [],
                    getSegmentationState: (index: number) => {
                        // The real syncState is reactive state; this reads the test's store the same way.
                        const state = fromStore(syncState);
                        return {
                            get syncState() {
                                return state.current;
                            },
                            loaded: over.slice?.loaded ?? Promise.resolve(),
                            isEmptyForSlice:
                                over.slice?.isEmptyForSlice ?? false,
                            mask: getMask(index),
                        };
                    },
                    isEmptyForSlice: () => false,
                    getMask,
                });
            }
            return items.get(key);
        },
    };
    const segmentationContext = new SegmentationContext(
        instanceId,
        0,
        {} as never,
        image as never,
    );
    const mainViewerContext = {
        segmentationContext,
        alpha: 1,
        saveOpacity: vi.fn(),
        getFeatureColor: () => [255, 0, 0],
        setFeatureColor: vi.fn(),
        isMaskingApplied: () => true,
        toggleMasking: vi.fn(),
        highlightedSegmentationItem: undefined,
        applyConnectedComponents: new SvelteSet<unknown>(),
        toggleConnectedComponents(item: unknown) {
            if (!this.applyConnectedComponents.delete(item))
                this.applyConnectedComponents.add(item);
        },
    };
    const viewerContext = {
        image,
        index: 0,
        axis: 0,
        activePanels: new SvelteSet<string>(),
    };
    const globalContext = {
        user: { id: ME },
        canEdit: (a: Segmentation) =>
            a.annotation_type === "grader_segmentation" && a.creator.id === ME,
        dialogue: null,
    };
    const context = new Map<string, unknown>([
        ["globalContext", globalContext],
        ["viewerContext", viewerContext],
        ["mainViewerContext", mainViewerContext],
    ]);
    return {
        context,
        sync,
        segmentationContext,
        viewerContext,
        mainViewerContext,
        globalContext,
    };
}
