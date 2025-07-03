import type { AnnotationData } from "$lib/datamodel/annotationData.svelte";
import { encodeNpy, NPYArray } from "$lib/utils/npy_loader";
import type { AbstractImage } from "./abstractImage";
import { DrawingHistory } from "./drawingHistory";
import { Base64Serializer } from "./imageEncoder";
import { BinarySegmentation, MultiClassSegmentation, MultiLabelSegmentation, ProbabilitySegmentation, QuestionableSegmentation, type DrawingArray, type PaintSettings, type Segmentation } from "./segmentation";
import { convert, type SegmentationType } from "./segmentationConverter";

export const constructors = {
    'Binary': BinarySegmentation,
    'DualBitMask': QuestionableSegmentation,
    'Probability': ProbabilitySegmentation,
    'MultiClass': MultiClassSegmentation,
    'MultiLabel': MultiLabelSegmentation,
}

export class SegmentationState {

    protected history: DrawingHistory<string>;
    public readonly segmentation: Segmentation;

    private isDrawing = Promise.resolve();

    constructor(
        readonly image: AbstractImage,
        readonly annotationData: AnnotationData
    ) {
        const annotationType = annotationData.annotation.annotationType;

        if ([2, 3, 4].includes(annotationType.id)) {
            this.segmentation = new QuestionableSegmentation(image, annotationData);
        } else if ([13, 17, 24].includes(annotationType.id)) {
            this.segmentation = new BinarySegmentation(image, annotationData);
        } else if ([14, 23, 25].includes(annotationType.id)) {
            this.segmentation = new ProbabilitySegmentation(image, annotationData)
        }

        // new:
        else if (annotationType.dataRepresentation in constructors) {
            this.segmentation = new constructors[annotationType.dataRepresentation](image, annotationData);
        } else {
            throw new Error(`Unsupported data representation: ${annotationType.dataRepresentation}`);
        }
        this.history = new DrawingHistory<string>(new Base64Serializer(annotationType.dataType, image.width, image.height));
        this.isDrawing = this.initialize();
    }

    private async initialize() {
        const data = await this.annotationData.file.load();
        if (data) {
            if (data instanceof NPYArray) {
                this.segmentation.importData(data.data as DrawingArray);
            } else {
                throw new Error('Unsupported data type', data);
            }
        }
        this.history.checkpoint(this.segmentation.exportData());
    }

    async draw(drawing: HTMLCanvasElement, settings: PaintSettings) {
        await this.isDrawing; // wait for previous drawing to finish
        this.segmentation.draw(drawing, settings);
        this.isDrawing = this.checkpoint();
    }

    async importOther(other: Segmentation) {
        await this.isDrawing; // wait for previous drawing to finish

        const data = other.exportData();

        const thisType = this.segmentation.constructor.name as SegmentationType;
        const otherType = other.constructor.name as SegmentationType;
        if (otherType instanceof ProbabilitySegmentation) {
            const threshold = other.i;
        }

        const dataConverted = convert(data, otherType, thisType,);

        this.segmentation.importData(data);
        this.isDrawing = this.checkpoint();
    }

    async checkpoint() {
        const data = this.segmentation.exportData();
        await updateServer(this.annotationData, data, this.image);
        this.history.checkpoint(data);
    }

    get canUndo() {
        return this.history.canUndo;
    }

    get canRedo() {
        return this.history.canRedo;
    }

    async undo() {
        const data = await this.history.undo();
        if (data) {
            this.segmentation.importData(data);
            await updateServer(this.annotationData, data, this.image);
        }
    }

    async redo() {
        const data = await this.history.redo();
        if (data) {
            this.segmentation.importData(data);
            await updateServer(this.annotationData, data, this.image);
        }
    }

    dispose() {
        // Clean up resources if needed
    }
}

function updateServer(annotationData: AnnotationData, data: DrawingArray, image: AbstractImage) {
    const npy = encodeNpy(data, [image.height, image.width]);
    return annotationData.file.update(npy);
}