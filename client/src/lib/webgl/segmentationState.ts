import type { AnnotationData } from "$lib/datamodel/annotationData.svelte";
import { encodeNpy, NPYArray } from "$lib/utils/npy_loader";
import type { AbstractImage } from "./abstractImage";
import { DrawingHistory } from "./drawingHistory";
import { Base64Serializer } from "./imageEncoder";
import { BinarySegmentation, MultiClassSegmentation, MultiLabelSegmentation, ProbabilitySegmentation, QuestionableSegmentation, type DrawingArray, type PaintSettings, type Segmentation } from "./segmentation";

export class SegmentationState {

    protected history: DrawingHistory<string>;
    public readonly segmentation: Segmentation;

    private isDrawing = Promise.resolve();

    constructor(
        readonly image: AbstractImage,
        readonly annotationData: AnnotationData
    ) {


        const annotationType = annotationData.annotation.annotationType;

        let dataType: 'R8' | 'R8UI' | 'R16UI' | 'R32UI' | 'R32F' = 'R8UI';
        if (annotationType.dataRepresentation == "BINARY" && annotationType.name == "Binary") {
            this.segmentation = new BinarySegmentation(image);
            dataType = 'R8UI';
        } else if (annotationType.dataRepresentation == "RG_MASK" && annotationType.name == "R/G mask") {
            this.segmentation = new QuestionableSegmentation(image);
            dataType = 'R8UI';
        } else if (annotationType.dataRepresentation == "FLOAT" && annotationType.name == "Probability") {
            this.segmentation = new ProbabilitySegmentation(image);
            dataType = 'R8';
        } else if (annotationType.dataRepresentation == "MULTI_CLASS" || annotationType.dataRepresentation == "MULTI_LABEL") {
            // Note: we cannot add features to the annotationType dynamically (it's not responsive after this point)
            const annotatedFeatures = annotationType.annotatedFeatures.$;
            const nFeatures = annotatedFeatures.length;
            if (nFeatures > 32) {
                throw new Error("MultiLabelSegmentation: too many features");
            }
            if (nFeatures > 16) {
                dataType = 'R32UI';
            } else if (nFeatures > 8) {
                dataType = 'R16UI';
            } else {
                dataType = 'R8UI';
            }
            if (annotationType.dataRepresentation == "MULTI_CLASS") {
                this.segmentation = new MultiClassSegmentation(image, annotationType, dataType);
            } else if (annotationType.dataRepresentation == "MULTI_LABEL") {
                this.segmentation = new MultiLabelSegmentation(image, annotationType, dataType);
            }

        } else {
            throw new Error(`Unsupported data representation: ${annotationType.dataRepresentation}`);
        }
        this.history = new DrawingHistory<string>(new Base64Serializer(dataType, image.width, image.height));
        this.isDrawing = this.initialize();
    }

    private async initialize() {
        const data = await this.annotationData.file.load();
        if (data) {
            if (data instanceof NPYArray) {
                this.segmentation.importData(data.data as DrawingArray);
                // } else if (data instanceof HTMLCanvasElement || data instanceof ImageBitmap) {
                //     this.segmentation.importImage(data);
            } else if (data instanceof ArrayBuffer) {
                this.segmentation.importData(data);
            } else {
                console.log(data);
                console.log(this.image.width, this.image.height);
                throw new Error('Unsupported data type', data);
            }
        }
        const ctx = this.image.getIOCtx();
        // this.segmentation.exportImage(ctx);
        // this.history.checkpoint(ctx.canvas.toDataURL());
        this.history.checkpoint(this.segmentation.exportData());
    }

    async draw(drawing: HTMLCanvasElement, settings: PaintSettings) {
        await this.isDrawing; // wait for previous drawing to finish
        this.segmentation.draw(drawing, settings);
        this.isDrawing = this.checkpoint();
    }

    importOther(other: Segmentation) {
        console.warn('importOther is not implemented');
        // const ctx = this.image.getIOCtx();
        // other.exportImage(ctx);
        // this.segmentation.importImage(ctx.canvas);

        // this.checkpoint();
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

async function getImage(imageString: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error('could not load image'));
        image.src = imageString;
    });
}

// export async function updateServer(image: AbstractImage, segmentation: Segmentation, annotationData: AnnotationData, data: DrawingArray) {


//     const ctx = image.getDrawingCtx();
//     segmentation.exportImage(ctx);
//     ctx.canvas.toDataURL();

//     let serverValue;
//     switch (annotationData.annotation.annotationType.dataRepresentation) {
//         case 'BINARY':
//         case 'RG_MASK':
//         case 'FLOAT':
//             serverValue = ctx.canvas;
//             break;
//         case 'MULTI_LABEL':
//         case 'MULTI_CLASS':
//             console.log('TODO: implement!')
//             break;
//     }
//     const dataURL = ctx.canvas.toDataURL();
//     if (serverValue) {
//         await annotationData.file.update(serverValue);
//     }

//     return dataURL;
// }
function updateServer(annotationData: AnnotationData, data: DrawingArray, image: AbstractImage) {
    const npy = encodeNpy(data, [image.height, image.width]);
    return annotationData.file.update(npy);
}