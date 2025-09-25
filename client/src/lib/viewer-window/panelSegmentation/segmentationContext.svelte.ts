
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import { SvelteMap, SvelteSet } from "svelte/reactivity";
import type { CreatorMeta, ModelMeta, SegmentationGET } from "../../../types/openapi_types";

export class SegmentationContext {

    // public readonly hiddenCreators = new SvelteSet<CreatorMeta | ModelMeta>();
    
    public creators = new SvelteMap<number, CreatorMeta>();
    public models = new SvelteMap<number, ModelMeta>();

    public creatorIds = $state<number[]>([]);
    public modelIds = $state<number[]>([]);

    public orderedCreators = $derived(this.creatorIds.map(id => this.creators.get(id) as CreatorMeta));
    public orderedModels = $derived(this.modelIds.map(id => this.models.get(id) as ModelMeta));

    public hiddenCreatorIds = new SvelteSet<number>();
    public hiddenModelIds = new SvelteSet<number>();
    // public hiddenCreators = $derived(Object.values(this.creators).filter(creator => this.hiddenCreatorIds.includes(creator.id)));
    // public hiddenModels = $derived(Object.values(this.models).filter(model => this.hiddenModelIds.includes(model.id)));

    public readonly visibleSegmentations = new SvelteSet<SegmentationGET>();

    public flipDrawErase = $state(false);
    public erodeDilateActive = $state(false);
    public questionableActive = $state(false);
    public brushRadius = $state(4);
    public segmentationItem: SegmentationItem | undefined = $state(undefined);
    public activeIndices: number | number[] = $state([]);

    constructor() { }

    toggleShowCreator(creator: CreatorMeta | ModelMeta) {
        if (this.hiddenCreatorIds.includes(creator.id)) {
            this.hiddenCreatorIds = this.hiddenCreatorIds.filter(id => id !== creator.id);
        } else {
            this.hiddenCreatorIds.push(creator.id);
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

