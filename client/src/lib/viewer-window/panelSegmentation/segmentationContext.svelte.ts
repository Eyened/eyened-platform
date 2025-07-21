
import type { Creator } from "$lib/datamodel/creator.svelte";
import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import { SvelteSet } from "svelte/reactivity";

export class SegmentationContext {

    public readonly hideCreators = new SvelteSet<Creator>();
    public readonly hideSegmentations = new SvelteSet<Segmentation>();

    public flipDrawErase = $state(false);
    public erodeDilateActive = $state(false);
    public questionableActive = $state(false);
    public brushRadius = $state(4);
    public segmentationItem: SegmentationItem | undefined = $state(undefined);
    public activeIndices: number | number[] = $state([]);

    constructor() { }


    toggleShow(segmentation: Segmentation) {
        if (this.hideSegmentations.has(segmentation)) {
            this.hideSegmentations.delete(segmentation);
        } else {
            this.hideSegmentations.add(segmentation);
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

