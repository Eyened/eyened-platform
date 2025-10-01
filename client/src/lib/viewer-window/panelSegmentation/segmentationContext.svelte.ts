
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import { SvelteMap } from "svelte/reactivity";
import type { CreatorMeta, ModelMeta, ModelSegmentationGET, SegmentationGET } from "../../../types/openapi_types";
import type { ViewerWindowContext } from "../viewerWindowContext.svelte";

export class SegmentationContext {

    public segmentations: SegmentationGET[];
    public modelSegmentations: ModelSegmentationGET[];
    
    public creators: SvelteMap<number, CreatorMeta>;
    public models: SvelteMap<number, ModelMeta>;

    public creatorHidden: SvelteMap<number, boolean>;
    public modelHidden: SvelteMap<number, boolean>;

    // public readonly visibleSegmentations = new SvelteSet<SegmentationGET>();
    public readonly segmentationsVisible: SvelteMap<number, boolean>;
    public readonly modelSegmentationsVisible: SvelteMap<number, boolean>;

    public readonly visibleSegmentations: (SegmentationGET | ModelSegmentationGET)[];

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
    ) { 
        // this.segmentations = $derived(instance.segmentations!.filter((s) => s.sparse_axis == axis));
        this.segmentations = $derived(viewerWindowContext.Segmentations.all.filter((s) => s.image_instance_id == instanceId && s.sparse_axis == axis));
        this.modelSegmentations = $derived(viewerWindowContext.ModelSegmentations.all.filter((s) => s.image_instance_id == instanceId && s.sparse_axis == axis));

        // this.modelSegmentations = $derived(instance.model_segmentations!.filter((s) => s.sparse_axis == axis));

        this.creators = $derived(new SvelteMap<number, CreatorMeta>(this.segmentations.map(s => [s.creator.id, s.creator])));

        this.models = $derived(new SvelteMap<number, ModelMeta>(this.modelSegmentations.map(s => [s.creator.id, s.creator])));

        this.creatorHidden = new SvelteMap<number, boolean>(this.segmentations.map(s => [s.creator.id, false]));
        this.modelHidden = new SvelteMap<number, boolean>(this.modelSegmentations.map(s => [s.creator.id, false]));
        
        this.segmentationsVisible = new SvelteMap<number, boolean>(this.segmentations.map(s => [s.id, true]));
        this.modelSegmentationsVisible = new SvelteMap<number, boolean>(this.modelSegmentations.map(s => [s.id, true]));

        this.visibleSegmentations = $derived(Array.from(this.segmentationsVisible.entries()).filter(([id, visible]) => visible).map(([id, visible]) => viewerWindowContext.Segmentations.store[id]));

        console.log(this.visibleSegmentations);
    }

    toggleShowCreator(creatorId: number) {
        const currentValue = this.creatorHidden.get(creatorId) ?? false;
        this.creatorHidden.set(creatorId, !currentValue);
    }

    toggleShowModel(modelId: number) {
        const currentValue = this.modelHidden.get(modelId) ?? false;
        this.modelHidden.set(modelId, !currentValue);
    }
        
    toggleShowSegmentation(segmentationId: number) {
        const currentValue = this.segmentationsVisible.get(segmentationId) ?? true;
        this.segmentationsVisible.set(segmentationId, !currentValue);
    }

    toggleShowModelSegmentation(modelSegmentationId: number) {
        const currentValue = this.modelSegmentationsVisible.get(modelSegmentationId) ?? true;
        this.modelSegmentationsVisible.set(modelSegmentationId, !currentValue);
    }

    hideAll() {
        // Hide all segmentations
        for (const [id] of this.segmentationsVisible) {
            this.segmentationsVisible.set(id, false);
        }
        
        // Hide all model segmentations
        for (const [id] of this.modelSegmentationsVisible) {
            this.modelSegmentationsVisible.set(id, false);
        }
    }

    showOnlySegmentation(segmentationId: number) {
        this.hideAll();
        
        // Show only the specified segmentation
        this.segmentationsVisible.set(segmentationId, true);
    }

    showOnlyModelSegmentation(modelSegmentationId: number) {

        this.hideAll();
        
        this.modelSegmentationsVisible.set(modelSegmentationId, true);
    }

    toggleActive(segmentationItem: SegmentationItem | undefined) {
        if (this.segmentationItem == segmentationItem) {
            this.segmentationItem = undefined;
        } else {
            this.segmentationItem = segmentationItem;
        }
    }
}

