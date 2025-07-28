
import type { Creator } from "$lib/datamodel/creator.svelte";
import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import { SvelteSet } from "svelte/reactivity";

export class SegmentationContext {

    public readonly hideCreators = new SvelteSet<Creator>();
    public readonly visibleSegmentations = new SvelteSet<Segmentation>();

    public flipDrawErase = $state(false);
    public erodeDilateActive = $state(false);
    public questionableActive = $state(false);
    public brushRadius = $state(4);
    public segmentationItem: SegmentationItem | undefined = $state(undefined);
    public activeIndices: number | number[] = $state([]);

    constructor() { }

    toggleShowCreator(creator: Creator) {
        if (this.hideCreators.has(creator)) {
            this.hideCreators.delete(creator);
        } else {
            this.hideCreators.add(creator);
        }
    }
        
    toggleShow(segmentation: Segmentation) {
        if (this.visibleSegmentations.has(segmentation)) {
            this.visibleSegmentations.delete(segmentation);
        } else {
            this.visibleSegmentations.add(segmentation);
        }
    }

    showOnly(segmentation: Segmentation) {
        this.visibleSegmentations.clear();
        this.visibleSegmentations.add(segmentation);
    }

    toggleActive(segmentationItem: SegmentationItem | undefined) {
        if (this.segmentationItem == segmentationItem) {
            this.segmentationItem = undefined;
        } else {
            this.segmentationItem = segmentationItem;
        }
    }
}

