import { getSegmentationData, getModelSegmentationData, updateSegmentationData } from "$lib/data/helpers";
import { encodeNpy, NPYArray } from "$lib/utils/npy_loader";
import type { ModelSegmentationGET, SegmentationGET, SegmentationDataRepresentation } from "../../types/openapi_types";
// SimpleDataRepresentation is a subset of SegmentationDataRepresentation
export type SimpleDataRepresentation = 'Binary' | 'DualBitMask' | 'Probability';
import type { AbstractImage } from "./abstractImage";
import { DrawingHistory } from "./drawingHistory.svelte";
import { Base64Serializer } from "./imageEncoder";
import { BinaryMask, MultiClassMask, MultiLabelMask, ProbabilityMask, QuestionableMask, type DrawingArray, type Mask, type PaintSettings } from "./mask.svelte";
import { convert } from "./segmentationConverter";

type MaskConstructor = new (image: AbstractImage, segmentation: SegmentationGET) => Mask;
export const constructors: Record<'Binary' | 'DualBitMask' | 'Probability' | 'MultiClass' | 'MultiLabel', MaskConstructor> = {
    'Binary': BinaryMask,
    'DualBitMask': QuestionableMask,
    'Probability': ProbabilityMask,
    'MultiClass': MultiClassMask,
    'MultiLabel': MultiLabelMask,
}

// manages the segmentation state (history, mask) for a single scan
export type SyncState = "synced" | "saving" | "error";

export class SegmentationState {

    protected history: DrawingHistory<string>;
    public readonly mask: Mask;

    private isDrawing = Promise.resolve();
    private hasInitialCheckpoint = false;
    private updateTimeout: ReturnType<typeof setTimeout> | null = null;
    private pendingUpdateResolve: (() => void) | null = null;
    public syncState = $state<SyncState>("synced");
    public isEmptyForSlice = $state(false);

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: SegmentationGET | ModelSegmentationGET,
        readonly scanNr: number,
        initialData?: DrawingArray,
    ) {
        this.mask = new constructors[segmentation.data_representation](image, segmentation as SegmentationGET);
        this.history = new DrawingHistory<string>(new Base64Serializer(segmentation.data_type, image.width, image.height));
        if (initialData) {
            this.mask.importData(initialData);
        } else {
            this.isDrawing = this.initialize();
        }
    }

    private ensureInitialCheckpoint() {
        if (!this.hasInitialCheckpoint) {
            this.history.checkpoint(this.mask.exportData());
            this.hasInitialCheckpoint = true;
        }
    }

    private async initialize() {
        // Load a single slice from the server
        const sparse_axis = this.segmentation.sparse_axis ?? undefined;
        const scan_nr = this.scanNr;

        let npyArray: NPYArray | null;
        if (this.segmentation.annotation_type == 'model_segmentation') {
            npyArray = await getModelSegmentationData(this.segmentation.id, { sparse_axis, scan_nr });
        } else {
            npyArray = await getSegmentationData(this.segmentation.id, { sparse_axis, scan_nr });
        }
        if (npyArray == null) {
            this.isEmptyForSlice = true;
            return;
        }
        this.mask.importData(npyArray.data as DrawingArray);
    }

    async draw(drawing: HTMLCanvasElement, settings: PaintSettings) {
        await this.isDrawing; // wait for previous drawing to finish
        this.ensureInitialCheckpoint();
        this.mask.draw(drawing, settings);
        this.isDrawing = this.checkpoint();
    }

    async importOther(other: Mask) {
        await this.isDrawing; // wait for previous drawing to finish
        this.ensureInitialCheckpoint();

        const data = other.exportData();

        const thisType = this.segmentation.data_representation as SegmentationDataRepresentation;
        const otherType = other.segmentation.data_representation as SegmentationDataRepresentation;
        const threshold = (255 * (other.segmentation.threshold ?? 0.5));

        function isSimpleRepresentation(t: SegmentationDataRepresentation): t is SimpleDataRepresentation {
            return t === 'Binary' || t === 'DualBitMask' || t === 'Probability';
        }

        if (isSimpleRepresentation(thisType) && isSimpleRepresentation(otherType)) {
            const dataConverted = convert(data, otherType, thisType, threshold);
            this.mask.importData(dataConverted);
        } else if (thisType === otherType) {
            this.mask.importData(data);
        } else {
            console.warn("SegmentationState.importOther: conversion not supported", otherType, "->", thisType);
        }

        this.isDrawing = this.checkpoint();
    }

    async checkpoint() {
        const data = this.mask.exportData();
        await this.updateServer();
        this.history.checkpoint(data);
    }

    get canUndo() {
        return this.history.canUndo;
    }

    get canRedo() {
        return this.history.canRedo;
    }

    async undo() {
        const data = await this.history.undo();
        if (data) {
            this.mask.importData(data);
            await this.updateServer();
        }
    }

    async redo() {
        const data = await this.history.redo();
        if (data) {
            this.mask.importData(data);
            await this.updateServer();
        }
    }

    updateServer() {
        // Clear existing timeout if one exists (debounce: cancel previous pending update)
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }
        
        // Resolve immediately for optimistic UI updates (don't block drawing)
        // The actual server call will be debounced and happen in the background
        const resolveImmediately = this.pendingUpdateResolve;
        if (resolveImmediately) {
            resolveImmediately();
        }
        
        // Set sync state to "saving" when update is triggered
        this.syncState = "saving";
        
        // Debounce: wait 2 seconds after last update before sending to server
        // The last call wins - it will export the current mask state, so no data is lost
        this.updateTimeout = setTimeout(async () => {
            try {
                const data = this.mask.exportData();
                const buffer = encodeNpy(data, [this.image.height, this.image.width]);
                const sparse_axis = this.segmentation.sparse_axis ?? undefined;
                const scan_nr = this.image.image_id.endsWith('proj') ? undefined : this.scanNr;
                await updateSegmentationData(this.segmentation.id, buffer, { sparse_axis, scan_nr });
                this.syncState = "synced";
            } catch (error) {
                this.syncState = "error";
                console.error("Failed to update segmentation data:", error);
            } finally {
                this.updateTimeout = null;
            }
        }, 2000);
        
        // Return a Promise that resolves immediately for optimistic updates
        return new Promise<void>((resolve) => {
            this.pendingUpdateResolve = resolve;
            // Resolve immediately so checkpoint() doesn't block
            resolve();
        });
    }

    dispose() {
        // Clear any pending update timeout
        // Note: We could optionally send the pending update immediately here,
        // but cancelling is safer to avoid race conditions during disposal
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
            this.updateTimeout = null;
        }
        // pendingUpdateResolve is not needed here since Promises resolve immediately
        this.mask.dispose();
        this.history.clear();
    }
}
