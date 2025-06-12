import type { Annotation } from "$lib/datamodel/annotation.svelte";
import type { Unsubscriber } from "svelte/store";
import type { AbstractImage } from "./abstractImage";
import { SegmentationState } from "./segmentationState";
import type { Segmentation, PaintSettings } from "./segmentation";
import { DeferredMap } from "$lib/utils/deferred";
import { AnnotationData } from "$lib/datamodel/annotationData.svelte";


export class SegmentationItem {

    unsubscribe: Unsubscriber;

    private segmentations: DeferredMap<number, SegmentationState> = new DeferredMap();

    constructor(
        readonly image: AbstractImage,
        readonly annotation: Annotation) {

        // automatically create a new SegmentationState if a new annotationData is added
        this.unsubscribe = annotation.annotationData.subscribe(data => {
            for (const annotationData of data) {
                const index = annotationData.scanNr;
                if (this.segmentations.has(index)) {
                    continue;
                }
                const segmentationState = new SegmentationState(this.image, annotationData);
                // this should resolve all the waiters for this key
                this.segmentations.set(index, segmentationState);
            }
        });
    }

    dispose() {
        this.unsubscribe();
    }

    getSegmentation(scanNr: number): Segmentation | undefined {
        return this.segmentations.getSync(scanNr)?.segmentation;
    }

    async getSegmentationState(scanNr: number, create: boolean = false): Promise<SegmentationState> {
        if (create && !this.segmentations.has(scanNr)) {
            const annotationPlane = "PRIMARY";
            let annotationData = this.annotation.annotationData.find(d => d.scanNr == scanNr && d.annotationPlane == annotationPlane);
            if (!annotationData) {
                await AnnotationData.createFrom(this.annotation, scanNr, annotationPlane);
            } else {
                console.warn("SegmentationItem.getSegmentationState: annotationData already exists", scanNr);
            }
        }
        return this.segmentations.get(scanNr);
    }

    async importOther(scanNr: number, segmentation: Segmentation) {
        const segmentationState = await this.getSegmentationState(scanNr, true);
        segmentationState.importOther(segmentation);
    }

    async draw(scanNr: number, drawing: HTMLCanvasElement, settings: PaintSettings) {
        const segmentationState = await this.getSegmentationState(scanNr, true);
        await segmentationState.draw(drawing, settings);
    }

    canUndo(scanNr: number) {
        return this.segmentations.getSync(scanNr)?.canUndo;
    }

    canRedo(scanNr: number) {
        return this.segmentations.getSync(scanNr)?.canRedo;
    }

    async undo(scanNr: number) {
        const segmentationState = this.segmentations.getSync(scanNr);
        if (segmentationState) {
            segmentationState.undo();
        } else {
            console.warn("SegmentationItem.undo: segmentationState not found", scanNr);
        }
    }

    async redo(scanNr: number) {
        const segmentationState = this.segmentations.getSync(scanNr);
        if (segmentationState) {
            segmentationState.redo();
        } else {
            console.warn("SegmentationItem.redo: segmentationState not found", scanNr);
        }
    }
}
