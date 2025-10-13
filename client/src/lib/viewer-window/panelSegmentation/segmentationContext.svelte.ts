
import { modelSegmentations, segmentations } from "$lib/data/stores.svelte";
import { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { SvelteMap, SvelteSet } from "svelte/reactivity";
import type { CreatorMeta, ModelMeta, ModelSegmentationGET, SegmentationGET } from "../../../types/openapi_types";
import type { ViewerWindowContext } from "../viewerWindowContext.svelte";

export type Segmentation = SegmentationGET | ModelSegmentationGET;

export class SegmentationContext {

    // Keep grader and model segmentations separate - cleaner!
    public graderSegmentations: SegmentationGET[] = $derived(
        Array.from(segmentations.values())
            .filter((s) => s.image_instance_id == this.instanceId && s.sparse_axis == this.axis)
    );
    
    public modelSegmentations: ModelSegmentationGET[] = $derived(
        Array.from(modelSegmentations.values())
            .filter((s) => s.image_instance_id == this.instanceId && s.sparse_axis == this.axis)
    );
    
    // Manage segmentation items (moved from AbstractImage)
    public readonly segmentationItems = new SvelteMap<number, SegmentationItem>();
    
    public creators: SvelteMap<number, CreatorMeta> = $derived(
        new SvelteMap(this.graderSegmentations.map(s => [s.creator.id, s.creator]))
    );

    public models: SvelteMap<number, ModelMeta> = $derived(
        new SvelteMap(this.modelSegmentations.map(s => [s.creator.id, s.creator]))
    );

    public creatorHidden = new SvelteMap<number, boolean>();
    public modelHidden = new SvelteMap<number, boolean>();

    // Use SvelteSet with raw objects - works because same references from global stores!
    public hiddenSegmentations = new SvelteSet<Segmentation>();

    public visibleGraderSegmentations: SegmentationGET[] = $derived(
        this.graderSegmentations.filter(s => !this.hiddenSegmentations.has(s))
    );

    public visibleModelSegmentations: ModelSegmentationGET[] = $derived(
        this.modelSegmentations.filter(s => !this.hiddenSegmentations.has(s))
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
    ) {}

    getSegmentationItem(segmentation: Segmentation): SegmentationItem {
        // Use id as key (unique per segmentation)
        if (this.segmentationItems.has(segmentation.id)) {
            return this.segmentationItems.get(segmentation.id)!;
        }

        // Create new segmentation item
        const segmentationItem = new SegmentationItem(this.image, segmentation);
        this.segmentationItems.set(segmentation.id, segmentationItem);
        return segmentationItem;
    }

    dispose() {
        for (const segmentationItem of this.segmentationItems.values()) {
            segmentationItem.dispose();
        }
        this.segmentationItems.clear();
    }

    toggleShowCreator(creatorId: number) {
        const currentValue = this.creatorHidden.get(creatorId) ?? false;
        this.creatorHidden.set(creatorId, !currentValue);
    }

    toggleShowModel(modelId: number) {
        const currentValue = this.modelHidden.get(modelId) ?? false;
        this.modelHidden.set(modelId, !currentValue);
    }
        
    toggleShowSegmentation(segmentation: Segmentation) {
        if (this.hiddenSegmentations.has(segmentation)) {
            this.hiddenSegmentations.delete(segmentation);
        } else {
            this.hiddenSegmentations.add(segmentation);
        }
    }

    hideAll() {
        // Hide all segmentations
        for (const seg of this.graderSegmentations) {
            this.hiddenSegmentations.add(seg);
        }
        for (const seg of this.modelSegmentations) {
            this.hiddenSegmentations.add(seg);
        }
    }

    showOnlySegmentation(segmentation: Segmentation) {
        this.hideAll();
        this.hiddenSegmentations.delete(segmentation);
    }

    toggleActive(segmentationItem: SegmentationItem | undefined) {
        if (this.segmentationItem == segmentationItem) {
            this.segmentationItem = undefined;
        } else {
            this.segmentationItem = segmentationItem;
        }
    }
}

