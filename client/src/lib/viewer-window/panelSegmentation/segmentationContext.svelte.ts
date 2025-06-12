import type { Annotation } from "$lib/datamodel/annotation.svelte";
import type { Creator } from "$lib/datamodel/creator.svelte";
import { SvelteSet } from "svelte/reactivity";

export class SegmentationContext {

    public readonly hideCreators = new SvelteSet<Creator>();
    public readonly hideAnnotations = new SvelteSet<Annotation>();

    public activeAnnotationID: number | undefined = $state();

    public flipDrawErase = $state(false);
    public erodeDilateActive = $state(false);
    public questionableActive = $state(false);
    public brushRadius = $state(4);

    constructor() { }


    toggleShow(annotation: Annotation) {
        if (this.hideAnnotations.has(annotation)) {
            this.hideAnnotations.delete(annotation);
        } else {
            this.hideAnnotations.add(annotation);
        }
    }

    toggleActive(annotation: Annotation) {
        if (this.activeAnnotationID == annotation.id) {
            this.activeAnnotationID = undefined;
        } else {
            this.activeAnnotationID = annotation.id;
        }
    }
}

