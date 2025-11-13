
import { modelSegmentations, segmentations } from "$lib/data/stores.svelte";
import { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { SvelteSet } from "svelte/reactivity";
import type { ModelSegmentationGET, SegmentationGET } from "../../../types/openapi_types";
import type { ViewerWindowContext } from "../viewerWindowContext.svelte";

export type Segmentation = SegmentationGET | ModelSegmentationGET;


export function getSegmentationKey(segmentation: Segmentation): string {
    return `${segmentation.annotation_type}_${segmentation.id}`;
}
export class SegmentationContext {

    public graderSegmentations: SegmentationGET[] = $derived(
        segmentations.filter((s) => s.image_instance_id == this.instanceId && s.sparse_axis == this.axis)
    );

    public modelSegmentations: ModelSegmentationGET[] = $derived(
        modelSegmentations.filter((s) => s.image_instance_id == this.instanceId && s.sparse_axis == this.axis)
    );

    public creatorVisible = new SvelteSet<number>();
    public modelVisible = $state(true);
    public shownSegmentations = new SvelteSet<string>();


    public visibleGraderSegmentations: SegmentationGET[] = $derived(
        this.graderSegmentations.filter(s => this.shownSegmentations.has(getSegmentationKey(s)))
    );

    public visibleModelSegmentations: ModelSegmentationGET[] = $derived(
        this.modelSegmentations.filter(s => this.shownSegmentations.has(getSegmentationKey(s)))
    );

    public flipDrawErase = $state(false);
    public erodeDilateActive = $state(false);
    public questionableActive = $state(false);
    public brushRadius = $state(4);
    public segmentationItem: SegmentationItem | undefined = $state(undefined);
    public activeIndices: number | number[] = $state([]);

    constructor(
        public readonly instanceId: number,
        public readonly axis: number,
        public readonly viewerWindowContext: ViewerWindowContext,
        public readonly image: AbstractImage,
    ) { }

    getSegmentationItem(segmentation: Segmentation): SegmentationItem {
        return this.image.getOrCreateSegmentationItem(segmentation);
    }

    getSegmentationItemById(segmentationId: number): SegmentationItem | undefined {
        const segmentation = this.graderSegmentations.find(s => s.id === segmentationId)
            || this.modelSegmentations.find(s => s.id === segmentationId);

        return segmentation ? this.image.getOrCreateSegmentationItem(segmentation) : undefined;
    }

    toggleShowCreator(creatorId: number) {
        if (this.creatorVisible.has(creatorId)) {
            this.creatorVisible.delete(creatorId);
        } else {
            this.creatorVisible.add(creatorId);
        }
    }

    toggleShowSegmentation(segmentation: Segmentation) {
        const key = getSegmentationKey(segmentation);

        if (this.shownSegmentations.has(key)) {
            this.shownSegmentations.delete(key);
        } else {
            this.shownSegmentations.add(key);
        }
    }

    toggleShowModel() {
        this.modelVisible = !this.modelVisible;
    }

    hideAll() {
        // Hide all segmentations by clearing the shown set
        this.shownSegmentations.clear();
    }

    showOnlySegmentation(segmentation: Segmentation) {
        const key = getSegmentationKey(segmentation);
        this.shownSegmentations.clear();
        this.shownSegmentations.add(key);
    }

    toggleActive(segmentationItem: SegmentationItem) {
        if (this.segmentationItem == segmentationItem) {
            this.segmentationItem = undefined;
        } else {
            this.segmentationItem = segmentationItem;
            this.shownSegmentations.add(getSegmentationKey(segmentationItem.segmentation));
        }

    }
}

