import type { Annotation } from "$lib/datamodel/annotation.svelte";
import type { Creator } from "$lib/datamodel/creator.svelte";
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import { SvelteSet } from "svelte/reactivity";

export class SegmentationContext {

    public readonly hideCreators = new SvelteSet<Creator>();
    public readonly hideAnnotations = new SvelteSet<Annotation>();

    public flipDrawErase = $state(false);
    public erodeDilateActive = $state(false);
    public questionableActive = $state(false);
    public brushRadius = $state(4);
    public segmentationItem: SegmentationItem | undefined = $state(undefined);
    public activeIndices: number | number[] = $state([]);

    constructor() { }


    toggleShow(annotation: Annotation) {
        if (this.hideAnnotations.has(annotation)) {
            this.hideAnnotations.delete(annotation);
        } else {
            this.hideAnnotations.add(annotation);
        }
    }

    toggleActive(segmentationItem: SegmentationItem | undefined) {
        if (this.segmentationItem == segmentationItem) {
            this.segmentationItem = undefined;
        } else {
            this.segmentationItem = segmentationItem;
        }
    }
}

