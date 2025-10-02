
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import { SvelteMap } from "svelte/reactivity";
import type { CreatorMeta, ModelMeta, ModelSegmentationGET, SegmentationGET } from "../../../types/openapi_types";
import type { ViewerWindowContext } from "../viewerWindowContext.svelte";

export type Segmentation = (SegmentationGET | ModelSegmentationGET) & {
    gid: string
}

export class SegmentationContext {

    public segmentations: Segmentation[];
    
    public creators: SvelteMap<number, CreatorMeta>;
    public models: SvelteMap<number, ModelMeta>;

    public creatorHidden: SvelteMap<number, boolean>;
    public modelHidden: SvelteMap<number, boolean>;

    // public readonly visibleSegmentations = new SvelteSet<SegmentationGET>();
    public readonly segmentationsVisible: SvelteMap<string, boolean>;
    // public readonly modelSegmentationsVisible: SvelteMap<number, boolean>;

    public readonly visibleSegmentations: Segmentation[];

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
        this.segmentations = $derived(
            [...viewerWindowContext.Segmentations.all, ...viewerWindowContext.ModelSegmentations.all]
            .filter((s) => s.image_instance_id == instanceId && s.sparse_axis == axis)
            .map(s => ({
                ...s,
                id: s.id,
                gid: `${s.annotation_type}-${s.id}`,
        })));

        this.creators = $derived(new SvelteMap<number, CreatorMeta>(
            this.segmentations.filter(s => s.annotation_type == "grader_segmentation")
            .map(s => [s.creator.id, s.creator])));

        this.models = $derived(new SvelteMap<number, ModelMeta>(
            this.segmentations.filter(s => s.annotation_type == "model_segmentation")
            .map(s => [s.creator.id, s.creator])));


        this.creatorHidden = new SvelteMap<number, boolean>(this.creators.keys().map(id => [id, false]));
        this.modelHidden = new SvelteMap<number, boolean>(this.models.keys().map(id => [id, false]));
        
        this.segmentationsVisible = new SvelteMap<string, boolean>(this.segmentations.map(s => [s.gid, true]));

        this.visibleSegmentations = $derived(this.segmentations.filter(s => this.segmentationsVisible.get(s.gid) ?? true));

    }

    toggleShowCreator(creatorId: number) {
        const currentValue = this.creatorHidden.get(creatorId) ?? false;
        this.creatorHidden.set(creatorId, !currentValue);
    }

    toggleShowModel(modelId: number) {
        const currentValue = this.modelHidden.get(modelId) ?? false;
        this.modelHidden.set(modelId, !currentValue);
    }
        
    toggleShowSegmentation(gid: string) {
        const currentValue = this.segmentationsVisible.get(gid) ?? true;
        this.segmentationsVisible.set(gid, !currentValue);
    }

    hideAll() {
        // Hide all segmentations
        for (const [gid] of this.segmentationsVisible) {
            this.segmentationsVisible.set(gid, false);
        }
    }

    showOnlySegmentation(gid: string) {
        this.hideAll();
        
        // Show only the specified segmentation
        this.segmentationsVisible.set(gid, true);
    }

    toggleActive(segmentationItem: SegmentationItem | undefined) {
        if (this.segmentationItem == segmentationItem) {
            this.segmentationItem = undefined;
        } else {
            this.segmentationItem = segmentationItem;
        }
    }
}

