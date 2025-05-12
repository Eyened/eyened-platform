import type { Annotation } from "$lib/datamodel/annotation";
import type { AnnotationData } from "$lib/datamodel/annotationData";
import type { Branch } from "$lib/types";
import type { AbstractImage } from "./abstractImage";
import { BinarySegmentation, MaskedSegmentation } from "./binarySegmentation";
import { MulticlassSegmentation, MultilabelSegmentation } from "./layerSegmentation";
import { ProbabilitySegmentation } from "./probabilitySegmentation.svelte";
import { SharedDataRG } from "./segmentationData";
import { SegmentationItem } from "./segmentationItem";

export interface Segmentation {
    id: string;
    annotation: Annotation;
    image: AbstractImage;
    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void;
    clear(scanNr: number): void;
    export(scanNr: number, ctx: CanvasRenderingContext2D): void;
    import(scanNr: number, canvas: HTMLCanvasElement): void;
    importOther(scanNr: number, other: Segmentation): void;
    dispose(): void;    
    initialize(annotationData:AnnotationData, dataRaw:any): void;
}


export class SegmentationController {

    public readonly sharedData = new Map<SharedDataRG, (BinarySegmentation | undefined)[]>();
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
    getSegmentationItem(annotation: Annotation): SegmentationItem {
        const id = `${annotation.id}`;
        if (this.segmentationItems.has(id)) {
            return this.segmentationItems.get(id)!;
        }
        return this.createSegmentation(annotation);
    }

    private createSegmentation(annotation: Annotation): SegmentationItem {
        const id = `${annotation.id}`;
        const type = getAnnotationType(annotation);
        let segmentation: Segmentation;
        if (type == 'Binary') {
            segmentation = this.createBinarySegmentation(id, annotation);
        } else if (type == 'Probability') {
            segmentation = new ProbabilitySegmentation(id, this.image, annotation);
        } else if (type == 'Multiclass') {
            segmentation = new MulticlassSegmentation(id, this.image, annotation);
        } else if (type == 'Multilabel') {
            segmentation = new MultilabelSegmentation(id, this.image, annotation);
        } else if (type == 'Masked') {
            // should be created instead via getMaskedSegmentation
            throw new Error('Should not be called for masked segmentations');
        } else {
            throw new Error('Unknown annotation type');
        }
        const segmentationItem = new SegmentationItem(this.image, annotation, segmentation);
        this.add(annotation, segmentationItem);
        return segmentationItem;
    }

    private createBinarySegmentation(id: string, annotation: Annotation) {
        const { data, index } = this.getNextDataIndex();
        const segmentation = new BinarySegmentation(id, this.image, annotation, data, index);
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
        
        const type = getAnnotationType(annotation);
        if (type != 'Masked') {
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
        const data = new SharedDataRG(this.image);
        const segmentations = Array.from({ length: data.size }) as (BinarySegmentation | undefined)[];
        this.sharedData.set(data, segmentations);
        return { data, index: 0 };
    }

}


function getAnnotationType(annotation: Annotation) {
    const { annotationType: { name, interpretation } } = annotation;
    if (interpretation == 'R/G mask' || interpretation == 'Binary mask') {
        if (['Segmentation 2D',
            'Segmentation OCT B-scan',
            'Segmentation OCT Enface',
            'Segmentation OCT Volume'].includes(name)) {
            return 'Binary';
        } else if (name == 'Segmentation 2D masked') {
            return 'Masked';
        }
    } else if (interpretation == 'Probability') {
        return 'Probability';
    } else if (interpretation == 'Label numbers') {
        return 'Multiclass';
    } else if (interpretation == 'Layer bits') {
        return 'Multilabel';
    }
    throw new Error('Unknown annotation type');
}