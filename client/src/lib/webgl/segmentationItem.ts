import type { Annotation } from "$lib/datamodel/annotation.svelte";
import { type Readable, type Unsubscriber } from "svelte/store";
import type { AbstractImage } from "./abstractImage";
import { SegmentationState } from "./segmentationState";
import type { Segmentation, PaintSettings } from "./segmentation";
import { DeferredMap } from "$lib/utils/deferred";
import { AnnotationData } from "$lib/datamodel/annotationData.svelte";
import { asyncReadable } from "$lib/utils";


export class SegmentationItem {

    unsubscribe: Unsubscriber;

    // mapping of scanNr to SegmentationState
    // a SegmentationState is created when a new annotationData is added
    private segmentationStates: DeferredMap<number, SegmentationState> = new DeferredMap();

    constructor(
        readonly image: AbstractImage,
        readonly annotation: Annotation) {

        // automatically create a new SegmentationState if a new annotationData is added
        this.unsubscribe = annotation.annotationData.subscribe(data => {
            for (const annotationData of data) {
                const index = annotationData.scanNr;
                if (this.segmentationStates.has(index)) {
                    continue;
                }
                const segmentationState = new SegmentationState(this.image, annotationData);
                // this should resolve all the waiters for this key
                this.segmentationStates.set(index, segmentationState);
            }
        });
    }

    dispose() {
        this.unsubscribe();
    }

    getSegmentation(scanNr: number): Segmentation | undefined {
        return this.segmentationStates.getSync(scanNr)?.segmentation;
    }

    async getSegmentationState(scanNr: number, create: boolean = false): Promise<SegmentationState> {
        if (create && !this.segmentationStates.has(scanNr)) {
            const annotationPlane = "PRIMARY";
            let annotationData = this.annotation.annotationData.find$(d => d.scanNr == scanNr && d.annotationPlane == annotationPlane);
            if (!annotationData) {
                await AnnotationData.createFrom(this.annotation, scanNr, annotationPlane);
            } else {
                console.warn("SegmentationItem.getSegmentationState: annotationData already exists", scanNr);
            }
        }
        return this.segmentationStates.get(scanNr);
    }

    async importOther(scanNr: number, segmentation: Segmentation) {
        const segmentationState = await this.getSegmentationState(scanNr, true);
        segmentationState.importOther(segmentation);
    }

    async draw(scanNr: number, drawing: HTMLCanvasElement, settings: PaintSettings) {
        const segmentationState = await this.getSegmentationState(scanNr, true);
        await segmentationState.draw(drawing, settings);
    }


    canUndo(scanNr: number): Readable<boolean> {
        return asyncReadable(this.segmentationStates.get(scanNr).then(state => state.canUndo), false);
    }

    canRedo(scanNr: number) {
        return asyncReadable(this.segmentationStates.get(scanNr).then(state => state.canRedo), false);
    }

    async undo(scanNr: number) {
        const segmentationState = this.segmentationStates.getSync(scanNr);
        if (segmentationState) {
            segmentationState.undo();
        } else {
            console.warn("SegmentationItem.undo: segmentationState not found", scanNr);
        }
    }

    async redo(scanNr: number) {
        const segmentationState = this.segmentationStates.getSync(scanNr);
        if (segmentationState) {
            segmentationState.redo();
        } else {
            console.warn("SegmentationItem.redo: segmentationState not found", scanNr);
        }
    }
}
