import type { AnnotationData } from "$lib/datamodel/annotationData.svelte";
import { NPYArray } from "$lib/utils/npy_loader";
import type { AbstractImage } from "./abstractImage";
import { DrawingHistory } from "./drawingHistory";
import { BinarySegmentation, MultiClassSegmentation, ProbabilitySegmentation, QuestionableSegmentation, type PaintSettings, type Segmentation } from "./segmentation";

export class SegmentationState {

    protected history: DrawingHistory;
    public readonly segmentation: Segmentation;

    private isDrawing = Promise.resolve();

    constructor(
        readonly image: AbstractImage,
        readonly annotationData: AnnotationData
    ) {
        this.history = new DrawingHistory();

        const annotationType = annotationData.annotation.annotationType;
        //TODO: use annotationType.dataRepresentation
        const is_binary = annotationType.id == 13;
        const is_rg_mask = annotationType.id == 2 || annotationType.name == 'R/G mask';
        const is_float = annotationType.id == 14;

        

        if (is_binary) {
            this.segmentation = new BinarySegmentation(image);
        } else if (is_rg_mask) {
            this.segmentation = new QuestionableSegmentation(image);
        } else if (is_float) {
            this.segmentation = new ProbabilitySegmentation(image);
        } else if (annotationType.id == 4) {
            // layer segmentation
            this.segmentation = new MultiClassSegmentation(image);
        } else {
            console.log(annotationType);
            // throw new Error(`Unsupported data representation: ${annotationType.dataRepresentation}`);
            console.log(`Unsupported data representation: ${annotationType.dataRepresentation}`);
            // this.segmentation = new BinarySegmentation(image);
        }

        this.isDrawing = this.initialize();
    }

    private async initialize() {
        const data = await this.annotationData.file.load();
        if (data) {
            if (data instanceof NPYArray) {
                this.segmentation.importData(data.data);
            } else if (data instanceof HTMLCanvasElement || data instanceof ImageBitmap) {
                this.segmentation.importImage(data);
            } else {
                console.log(data);
                throw new Error('Unsupported data type', data);
            }
        } 
        console.log('initialize', data);
        const ctx = this.image.getIOCtx();
        this.segmentation.exportImage(ctx);
        this.history.checkpoint(ctx.canvas.toDataURL());
    }

    async draw(drawing: HTMLCanvasElement, settings: PaintSettings) {
        await this.isDrawing; // wait for previous drawing to finish
        console.log('draw');
        this.segmentation.draw(drawing, settings);
        this.isDrawing = this.checkpoint();
    }

    importOther(other: Segmentation) {
        const ctx = this.image.getIOCtx();
        other.exportImage(ctx);
        this.segmentation.importImage(ctx.canvas);
        
        this.checkpoint();
    }

    async checkpoint() {
        console.log('checkpoint');
        const dataURL = await updateServer(this.image, this.segmentation, this.annotationData);
        this.history.checkpoint(dataURL);
    }

    get canUndo() {
        return this.history.canUndo;
    }

    get canRedo() {
        return this.history.canRedo;
    }

    async undo() {
        const imageString = this.history.undo();
        if (imageString) {
            const image = await getImage(imageString);
            this.segmentation.importImage(image);
            await updateServer(this.image, this.segmentation, this.annotationData);
        }
    }

    async redo() {
        const imageString = this.history.redo();
        if (imageString) {
            const canvas = await getImage(imageString);
            this.segmentation.importImage(canvas);
            await updateServer(this.image, this.segmentation, this.annotationData);
        }
    }

    dispose() {
        // Clean up resources if needed
    }
}

async function getImage(imageString: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error('could not load image'));
        image.src = imageString;
    });
}

export async function updateServer(image: AbstractImage, segmentation: Segmentation, annotationData: AnnotationData): Promise<string> {


    const ctx = image.getDrawingCtx();
    segmentation.exportImage(ctx);
    ctx.canvas.toDataURL();

    let serverValue;
    switch (annotationData.annotation.annotationType.dataRepresentation) {
        case 'BINARY':
        case 'RG_MASK':
        case 'FLOAT':
            serverValue = ctx.canvas;
            break;
        case 'MULTI_LABEL':
        case 'MULTI_CLASS':
            console.log('TODO: implement!')
            break;
    }
    const dataURL = ctx.canvas.toDataURL();
    if (serverValue) {
        await annotationData.file.update(serverValue);
    }

    return dataURL;
}