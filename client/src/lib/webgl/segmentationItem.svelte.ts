import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
import type { AbstractImage } from "./abstractImage";
import { SegmentationState } from "./segmentationState";
import type { Mask, PaintSettings } from "./mask.svelte";
import { SvelteMap } from "svelte/reactivity";

// manages the segmentation states (one per scan) for a single segmentation
export class SegmentationItem {

    // mapping of scanNr to SegmentationState
    segmentationStates: SvelteMap<number, SegmentationState> = new SvelteMap();
    loading: boolean = $state(false);
    ready: Promise<void> | null = null;

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: Segmentation) {

        if (Array.isArray(this.segmentation.scanIndices) && this.segmentation.scanIndices.length < 5) {
            for (const scanNr of this.segmentation.scanIndices ?? Array.from({ length: this.image.depth }, (_, i) => i)) {
                this.getSegmentationState(scanNr, true);
            }
        } else {
            this.ready = this.loadFull();
        }
    }

    private async loadFull(): Promise<void> {
        try {
            this.loading = true;
            const array = await this.segmentation.loadData();
            const shape = array.shape as number[];
            // Expecting [depth, height, width]
            const depth = shape[0] ?? this.image.depth;
            const height = shape[1] ?? this.image.height;
            const width = shape[2] ?? this.image.width;
            const planeSize = height * width;

            const scanIndices = this.segmentation.scanIndices ?? Array.from({ length: depth }, (_, i) => i);
            for (const scanNr of scanIndices) {
                const start = scanNr * planeSize;
                const end = start + planeSize;
                const slice = (array.data as any).subarray(start, end);
                this.getSegmentationState(scanNr, true, slice);
            }
        } catch (error) {
            console.error('SegmentationItem loadBulkIfNeeded failed', error);
        } finally {
            this.loading = false;
        }
    }

    getMask(scanNr: number): Mask | undefined {
        return this.segmentationStates.get(scanNr)?.mask;
    }

    getSegmentationState(scanNr: number, create: boolean = false, initialData?: Uint8Array | Uint16Array | Uint32Array | Float32Array): SegmentationState | undefined {

        if (create && !this.segmentationStates.has(scanNr)) {
            const segmentationState = new SegmentationState(this.image, this.segmentation, scanNr, initialData);
            this.segmentationStates.set(scanNr, segmentationState);
        }
        return this.segmentationStates.get(scanNr)!;
    }

    async importOther(scanNr: number, mask: Mask) {
        const segmentationState = this.getSegmentationState(scanNr, true)!;
        segmentationState.importOther(mask);
    }

    async draw(scanNr: number, drawing: HTMLCanvasElement, settings: PaintSettings) {
        const segmentationState = this.getSegmentationState(scanNr, true)!;
        await segmentationState.draw(drawing, settings);
    }

    async undo(scanNr: number) {
        const segmentationState = this.segmentationStates.get(scanNr);
        if (segmentationState) {
            segmentationState.undo();
        } else {
            console.warn("SegmentationItem.undo: segmentationState not found", scanNr);
        }
    }

    async redo(scanNr: number) {
        const segmentationState = this.segmentationStates.get(scanNr);
        if (segmentationState) {
            segmentationState.redo();
        } else {
            console.warn("SegmentationItem.redo: segmentationState not found", scanNr);
        }
    }

    dispose() {
        for (const segmentationState of this.segmentationStates.values()) {
            segmentationState.dispose();
        }
        this.segmentationStates.clear();
    }
}
