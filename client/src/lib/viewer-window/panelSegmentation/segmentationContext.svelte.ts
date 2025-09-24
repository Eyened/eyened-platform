
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import { SvelteSet } from "svelte/reactivity";
import type { CreatorMeta, ModelMeta, SegmentationGET } from "../../../types/openapi_types";

export class SegmentationContext {

    public readonly hideCreators = new SvelteSet<CreatorMeta | ModelMeta>();
    public readonly visibleSegmentations = new SvelteSet<SegmentationGET>();

    public flipDrawErase = $state(false);
    public erodeDilateActive = $state(false);
    public questionableActive = $state(false);
    public brushRadius = $state(4);
    public segmentationItem: SegmentationItem | undefined = $state(undefined);
    public activeIndices: number | number[] = $state([]);

    constructor() { }

    toggleShowCreator(creator: CreatorMeta | ModelMeta) {
        if (this.hideCreators.has(creator)) {
            this.hideCreators.delete(creator);
        } else {
            this.hideCreators.add(creator);
        }
    }
        
    toggleShow(segmentation: SegmentationGET) {
        if (this.visibleSegmentations.has(segmentation)) {
            this.visibleSegmentations.delete(segmentation);
        } else {
            this.visibleSegmentations.add(segmentation);
        }
    }

    showOnly(segmentation: SegmentationGET) {
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

