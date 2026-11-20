import {
    SegmentationContext,
    type Segmentation,
} from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { SyncState } from "$lib/webgl/segmentationState.svelte";
import { SvelteMap, SvelteSet } from "svelte/reactivity";
import { fromStore, writable, type Writable } from "svelte/store";
import { vi } from "vitest";
import { MeasureTool } from "$lib/viewer/tools/Measure.svelte";
import { BlendStyles } from "./blendStyles";
import { GridLayers } from "./gridLayers.svelte";
import { PointsetState } from "./pointsets";
import { twinNumbers, type ImageMeta } from "$lib/workspace/imageMeta";
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

/** A synthetic loaded 2D image of patient 1. */
export function fakeImage(
    id: string,
    over: {
        modality?: string;
        date?: string;
        laterality?: string;
        device?: { manufacturer: string; model: string };
    } = {},
) {
    return {
        image_id: id,
        is2D: true,
        is3D: false,
        width: 100,
        height: 100,
        supportsColorRenderModes: true,
        instance: {
            id,
            patient: { id: 1 },
            study: { id: 2, date: over.date ?? "2024-03-12" },
            laterality: over.laterality ?? "R",
            modality: over.modality ?? "Autofluorescence",
            device: over.device ?? {
                manufacturer: "Heidelberg",
                model: "Spectralis",
            },
        },
    };
}

/** The window fake; two calls share one, as two viewports share their window. */
export interface TestWindow {
    pointsets: PointsetState;
    blendStyles: BlendStyles;
    images: SvelteMap<string, unknown>;
    registration: unknown;
    topViewers: Map<unknown, unknown>;
    readonly twins: Map<string, string>;
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
        /** The image's model keypoints, for the AI grid. */
        cfKeypoints?: { fovea_xy: number[]; disc_edge_xy: number[] };
        /** Image ids registered to this one. */
        linked?: string[];
        /** Other loaded images, in strip order. */
        images?: ReturnType<typeof fakeImage>[];
        /** A window from an earlier call. */
        win?: TestWindow;
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
        image_id: instanceId,
        supportsColorRenderModes: true,
        instance: {
            id: instanceId,
            patient: { id: 1 },
            study: { id: 2, date: "2022-05-10" },
            laterality: "R",
            modality: "ColorFundus",
            device: { manufacturer: "Topcon", model: "Maestro2" },
            cf_keypoints: over.cfKeypoints ?? null,
        },
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
    const registration = {
        getLinkedImgIds: () => new Set(over.linked ?? []),
    };
    const others = over.images ?? [];
    const win: TestWindow = over.win ?? {
        pointsets: new PointsetState(),
        blendStyles: new BlendStyles(),
        images: new SvelteMap<string, unknown>(),
        registration,
        topViewers: new Map(),
        // As ViewerWindowContext: twin numbers over the window's images in strip order.
        get twins() {
            return twinNumbers(
                workspace.catalogue,
                (i) =>
                    (win.images.get(i) as { instance: ImageMeta } | undefined)
                        ?.instance,
            );
        },
    };
    for (const loaded of [image, ...others])
        win.images.set(loaded.image_id, loaded);
    // Reactive like the real Workspace, so a section re-renders after it writes the fraction.
    const fraction = fromStore(writable(0.85));
    const workspace = {
        catalogue: [image.image_id, ...others.map((i) => i.image_id)],
        arm: vi.fn(),
        armedTool: null,
        get etdrsFraction() {
            return fraction.current;
        },
        set etdrsFraction(value: number) {
            fraction.current = value;
        },
        etdrsSlot: 0,
    };
    const viewerContext = {
        image,
        index: 0,
        axis: 0,
        activePanels: new SvelteSet<string>(),
        addOverlay: vi.fn(() => vi.fn()),
        viewerWindowContext: win,
    };
    const globalContext = {
        user: { id: ME },
        canEdit: (a: { annotation_type?: string; creator: { id: number } }) =>
            a.annotation_type !== "model_segmentation" && a.creator.id === ME,
        dialogue: null,
    };
    const grids = new GridLayers(viewerContext as never, registration as never, {
        get radiusFraction() {
            return workspace.etdrsFraction;
        },
    });
    const measure = new MeasureTool(image as never);
    const context = new Map<string, unknown>([
        ["globalContext", globalContext],
        ["viewerContext", viewerContext],
        ["mainViewerContext", mainViewerContext],
        ["workspace", workspace],
    ]);
    return {
        context,
        sync,
        segmentationContext,
        viewerContext,
        mainViewerContext,
        globalContext,
        grids,
        measure,
        win,
        workspace,
    };
}
