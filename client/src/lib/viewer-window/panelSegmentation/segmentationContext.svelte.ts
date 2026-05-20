
import { modelSegmentations, segmentations } from "$lib/data/stores.svelte";
import { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { SvelteMap, SvelteSet } from "svelte/reactivity";
import type { ModelSegmentationGET, SegmentationGET } from "../../../types/openapi_types";
import type { ViewerWindowContext } from "../viewerWindowContext.svelte";

export type Segmentation = SegmentationGET | ModelSegmentationGET;


export function getSegmentationKey(segmentation: Segmentation): string {
    return `${segmentation.annotation_type}_${segmentation.id}`;
}
function matchesAxis(segmentation: Segmentation, axis: number): boolean {
    return segmentation.sparse_axis == null || segmentation.sparse_axis == undefined || segmentation.sparse_axis == axis;
}
export class SegmentationContext {

    public graderSegmentations: SegmentationGET[] = $derived(
        segmentations.filter((s) => s.image_id == this.instanceId && matchesAxis(s, this.axis))
    );

    public modelSegmentations: ModelSegmentationGET[] = $derived(
        modelSegmentations.filter((s) => s.image_id == this.instanceId && matchesAxis(s, this.axis))
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
    /** True while a segmentation stroke is in progress (pointer/keyboard). Used by multi-label overlay. */
    public isDrawing = $state(false);

    /** Per-segmentation bitmask: bit (i-1) = 1 means subfeature i is shown in multi-class / multi-label shaders. */
    private visibleFeatureMaskBySegmentationKey = new SvelteMap<string, number>();

    constructor(
        public readonly instanceId: string,
        public readonly axis: number,
        public readonly viewerWindowContext: ViewerWindowContext,
        public readonly image: AbstractImage,
    ) {
    }

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

    private static readonly ALL_FEATURES_VISIBLE = 0xffffffff >>> 0;

    getVisibleFeatureMask(segmentation: Segmentation): number {
        const key = getSegmentationKey(segmentation);
        const v = this.visibleFeatureMaskBySegmentationKey.get(key);
        return v === undefined ? SegmentationContext.ALL_FEATURES_VISIBLE : v >>> 0;
    }

    isFeatureLayerVisible(segmentation: Segmentation, featureIndex: number): boolean {
        const bit = (1 << (featureIndex - 1)) >>> 0;
        return (this.getVisibleFeatureMask(segmentation) & bit) !== 0;
    }

    toggleFeatureLayerVisibility(segmentation: Segmentation, featureIndex: number): void {
        const key = getSegmentationKey(segmentation);
        const cur = this.getVisibleFeatureMask(segmentation) >>> 0;
        const bit = (1 << (featureIndex - 1)) >>> 0;
        this.visibleFeatureMaskBySegmentationKey.set(key, (cur ^ bit) >>> 0);
    }
}

