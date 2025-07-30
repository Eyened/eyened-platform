import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
import type { AbstractImage } from "./abstractImage";
import { SegmentationState } from "./segmentationState";
import type { Mask, PaintSettings } from "./mask.svelte";
import { SvelteMap } from "svelte/reactivity";

// manages the segmentation states (one per scan) for a single segmentation
export class SegmentationItem {

    // mapping of scanNr to SegmentationState
    segmentationStates: SvelteMap<number, SegmentationState> = new SvelteMap();

    constructor(
        readonly image: AbstractImage,
        readonly segmentation: Segmentation) {

        for (const scanNr of this.segmentation.scanIndices ?? Array.from({ length: this.image.depth }, (_, i) => i)) {
            this.getSegmentationState(scanNr, true);
        }
    }

    getMask(scanNr: number): Mask | undefined {
        return this.segmentationStates.get(scanNr)?.mask;
    }

    getSegmentationState(scanNr: number, create: boolean = false): SegmentationState | undefined {

        if (create && !this.segmentationStates.has(scanNr)) {
            const segmentationState = new SegmentationState(this.image, this.segmentation, scanNr);
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
