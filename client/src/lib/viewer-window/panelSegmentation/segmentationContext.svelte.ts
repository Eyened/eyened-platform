import type { Annotation } from "$lib/datamodel/annotation";
import type { Creator } from "$lib/datamodel/creator";
import type { Feature } from "$lib/datamodel/feature";
import type { Segmentation } from "$lib/webgl/SegmentationController";
import { SvelteSet } from "svelte/reactivity";

export class SegmentationContext {
    public readonly hideCreators = new SvelteSet<Creator>();
    public readonly hideFeatures = new SvelteSet<Feature>();
    public readonly hideAnnotations = new SvelteSet<Annotation>();
    public readonly hideSegmentations = new SvelteSet<Segmentation>();
    public activeSegmentation: Segmentation | undefined = $state();


    public flipDrawErase = $state(false);
    public erodeDilateActive = $state(false);
    public questionableActive = $state(false);
    public brushRadius = $state(4);

    constructor() { }


    toggleShow(segmentation: Segmentation) {
        if (this.hideSegmentations.has(segmentation)) {
            this.hideSegmentations.delete(segmentation);
        } else {
            this.hideSegmentations.add(segmentation);
        }
    }

    toggleActive(segmentation: Segmentation) {
        if (this.activeSegmentation == segmentation) {
            this.activeSegmentation = undefined;
        } else {
            this.activeSegmentation = segmentation;
        }
    }
}

