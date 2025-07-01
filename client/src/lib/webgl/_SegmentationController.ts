import type { Annotation } from "$lib/datamodel/annotation.svelte";
import type { AnnotationData, AnnotationPlane } from "$lib/datamodel/annotationData.svelte";
import type { DataRepresentation } from "$lib/datamodel/annotationType.svelte";
import type { Branch } from "$lib/types";
import type { AbstractImage } from "./abstractImage";
import type { Segmentation } from "./baseSegmentation";
import { BinarySegmentation, MaskedSegmentation } from "./binarySegmentation";
import { MulticlassSegmentation, MultilabelSegmentation } from "./layerSegmentation";
import { ProbabilitySegmentation } from "./probabilitySegmentation.svelte";
import { SharedData } from "./_segmentationData";
import { SegmentationItem } from "./segmentationItem";


export class SegmentationController {

    public readonly sharedData = new Map<SharedData, (BinarySegmentation | undefined)[]>();
    public readonly segmentationItems = new Map<string, SegmentationItem>();
    private readonly annotationSegmentations: Map<Annotation, Segmentation[]> = new Map();
    public readonly allSegmentations: Segmentation[] = [];

    constructor(readonly image: AbstractImage) { }


    /**
     * Returns the BinarySegmentation for the given annotation (if it has the correct type)
     * Segmentations are cached, so that the same segmentation is always returned
     * This way, they can be reused in multiple viewers or when the segmentation panel is closed and reopened
     * 
     * If the segmentation does not exist, it is created.
     * 
     * Note: in the current implementation, the segmentation is never disposed
     * This memory leak may become a problem if many segmentations are created for many images
     * 
     * 
     * @param annotation 
     * @returns 
     */
    getSegmentationItem(annotation: Annotation, viewerPlane: AnnotationPlane): SegmentationItem {
        const id = `${annotation.id}_${viewerPlane}`;
        if (this.segmentationItems.has(id)) {
            return this.segmentationItems.get(id)!;
        }
        const type = annotation.annotationType.dataRepresentation;

        let segmentation: Segmentation;
        if (type == 'BINARY' || type == 'RG_MASK') {
            segmentation = this.createBinarySegmentation(id, annotation, viewerPlane);
        } else if (type == 'FLOAT') {
            segmentation = new ProbabilitySegmentation(id, this.image, annotation, viewerPlane);
        } else if (type == 'MULTI_CLASS') {
            segmentation = new MulticlassSegmentation(id, this.image, annotation, viewerPlane);
        } else if (type == 'MULTI_LABEL') {
            segmentation = new MultilabelSegmentation(id, this.image, annotation, viewerPlane);
        } else {
            throw new Error('Unknown annotation type');
        }

        const segmentationItem = new SegmentationItem(this.image, annotation, segmentation);
        this.add(annotation, segmentationItem);

        return segmentationItem;
    }

    private createBinarySegmentation(id: string, annotation: Annotation, viewerPlane: AnnotationPlane) {
        const { data, index } = this.getNextDataIndex();
        const segmentation = new BinarySegmentation(id, this.image, annotation, data, index, viewerPlane);
        this.sharedData.get(data)![index] = segmentation;
        return segmentation;
    }

    /**
     * Stores the segmentation in the cache 
     * @param annotation 
     * @param segmentation 
     */
    private add(annotation: Annotation, segmentationItem: SegmentationItem) {
        const segmentation = segmentationItem.segmentation;
        this.segmentationItems.set(segmentation.id, segmentationItem);
        this.allSegmentations.push(segmentation);
        // Add to annotationSegmentations (there can be multiple segmentations for one annotation)
        let lst = this.annotationSegmentations.get(annotation);
        if (lst) {
            lst.push(segmentation);
        } else {
            this.annotationSegmentations.set(annotation, [segmentation]);
        }
    }


    /**
     * A single annotation can have multiple masked segmentations
     * Therefore, the branch is used to distinguish between them, and this call is different from getSegmentation
     * 
     * @param maskAnnotation 
     * @param branch 
     * @returns MaskedSegmentation
     */
    getMaskedSegmentation(annotation: Annotation, maskAnnotation: Annotation, branch: Branch): SegmentationItem {
        const id = `${annotation.id}-${branch.id}`;
        if (this.segmentationItems.has(id)) {
            return this.segmentationItems.get(id)!;
        }

        const type = annotation.annotationType.dataRepresentation;
        throw new Error(`not implemented`);
        if (type != 'RG_MASK') {
            throw new Error(`Annotation is not masked: ${type} ${annotation.id}`);
        }
        const maskSegmentationItem = this.getSegmentationItem(maskAnnotation);
        const maskSegmentation = maskSegmentationItem.segmentation;
        if (!(maskSegmentation instanceof BinarySegmentation)) {
            throw new Error('Mask annotation is not binary');
        }

        const { data, index } = this.getNextDataIndex();
        const segmentation = new MaskedSegmentation(id, this.image, annotation, data, index, maskSegmentation, branch);
        this.sharedData.get(data)![index] = segmentation;
        const segmentationItem = new SegmentationItem(this.image, annotation, segmentation);

        this.add(annotation, segmentationItem);

        return segmentationItem;
    }


    removeAnnotation(annotation: Annotation) {
        const segmentations = this.annotationSegmentations.get(annotation);
        if (segmentations) {
            for (const segmentation of segmentations) {
                this.removeSegmentation(segmentation);
            }
            this.annotationSegmentations.delete(annotation);
        }
    }

    removeSegmentation(segmentation: Segmentation) {
        segmentation.dispose();
        this.segmentationItems.delete(segmentation.id);
        const index = this.allSegmentations.indexOf(segmentation);
        if (index >= 0) {
            this.allSegmentations.splice(index, 1);
        }

        const { annotation } = segmentation;
        const segmentations = this.annotationSegmentations.get(annotation);
        if (segmentations) {
            const index = segmentations.indexOf(segmentation);
            if (index >= 0) {
                segmentations.splice(index, 1);
            }
        } else {
            throw new Error('Segmentation not found');
        }
        if (segmentation instanceof BinarySegmentation) {
            const array = this.sharedData.get(segmentation.data)!;
            for (let i = 0; i < array.length; i++) {
                if (array[i] == segmentation) {
                    array[i] = undefined;
                }
            }
            // TODO: dispose data if no segmentations are using it?

        }
    }

    /**
     * Checks all shared data for the next free index
     * If no free index is found, a new SharedDataRG is created
     * 
     * @returns {data: SharedDataRG, index: number}
     */
    private getNextDataIndex() {
        for (const [data, segmentations] of this.sharedData.entries()) {
            for (let i = 0; i < data.size; i++) {
                if (segmentations[i] == undefined) {
                    return { data, index: i };
                }
            }
        }
        // No free space found, create new data
        const data = new SharedData(this.image, this.image.width, this.image.height, this.image.depth);
        const segmentations = Array.from({ length: data.size }) as (BinarySegmentation | undefined)[];
        this.sharedData.set(data, segmentations);
        return { data, index: 0 };
    }

}