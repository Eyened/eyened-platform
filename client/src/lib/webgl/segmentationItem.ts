import type { Annotation } from "$lib/datamodel/annotation";
import type { Unsubscriber } from "svelte/store";
import type { Segmentation } from "./SegmentationController";
import { UndoRedo } from "./drawingHistory";
import type { AnnotationData } from "$lib/datamodel/annotationData";
import type { AbstractImage } from "./abstractImage";
import { data } from "$lib/datamodel/model";
import { getImage } from "$lib/data-loading/imageLoader";
import { MaskedSegmentation } from "./binarySegmentation";
import { MulticlassSegmentation, MultilabelSegmentation } from "./layerSegmentation";

export class SegmentationItem {

    unsubscribe: Unsubscriber;
    private initialized = new Set<AnnotationData>;
    protected history: UndoRedo;

    constructor(
        readonly image: AbstractImage,
        readonly annotation: Annotation,
        readonly segmentation: Segmentation) {

        this.history = new UndoRedo(image.depth);

        // if a new annotationData is added, it should be imported
        this.unsubscribe = annotation.annotationDatas.subscribe(datas => {
            datas.forEach(this.importScan.bind(this));
        });

    }

    protected async importScan(annotationData: AnnotationData) {
        if (this.initialized.has(annotationData)) {
            return;
        }

        this.initialized.add(annotationData);

        const data = await annotationData.value.load();
        if (!data) {
            // no data received from server
            return;
        }
        this.initialize(annotationData, data);
    }

    private initialize(annotationData: AnnotationData, dataRaw: any) {
        const { scanNr } = annotationData;

        this.segmentation.initialize(annotationData, dataRaw);


        // make a checkpoint of current state
        if (this.history.isInitialized(scanNr)) {
            console.warn('History already initialized', scanNr);
        } else {
            const ctx = this.image.getIOCtx();
            this.segmentation.export(scanNr, ctx);
            this.history.initialize(scanNr, ctx.canvas.toDataURL());
        }
    }

    dispose() {
        this.unsubscribe();
    }

    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any) {
        // if not initialized, create a checkpoint before drawing
        if (!this.history.isInitialized(scanNr)) {
            const ctx = this.image.getIOCtx();
            this.segmentation.export(scanNr, ctx);
            this.history.initialize(scanNr, ctx.canvas.toDataURL());
        }
        this.segmentation.draw(scanNr, drawing, settings);
        this.checkpoint(scanNr);
    }

    importOther(scanNr: number, other: Segmentation) {
        this.segmentation.importOther(scanNr, other);
        this.checkpoint(scanNr);
    }

    async checkpoint(scanNr: number) {
        const canvas = await updateServer(this.segmentation, scanNr);
        this.history.checkpoint(scanNr, canvas.toDataURL());
    }

    canUndo(scanNr: number) {
        return this.history.canUndo(scanNr);
    }

    canRedo(scanNr: number) {
        return this.history.canRedo(scanNr);
    }

    async undo(scanNr: number) {
        const canvasString = this.history.undo(scanNr);
        if (canvasString) {
            const canvas = await getImage(canvasString);
            this.segmentation.import(scanNr, canvas);
            updateServer(this.segmentation, scanNr);
        }
    }

    async redo(scanNr: number) {
        const canvasString = this.history.redo(scanNr);
        if (canvasString) {
            const canvas = await getImage(canvasString);
            this.segmentation.import(scanNr, canvas);
            updateServer(this.segmentation, scanNr);
        }
    }
}

async function getAnnotationData(segmentation: Segmentation, scanNr: number) {
    const { annotation } = segmentation;
    let annotationData = annotation.annotationDatas.find(d => d.scanNr == scanNr);
    let mediaType = 'image/png';
    if (segmentation instanceof MulticlassSegmentation || segmentation instanceof MultilabelSegmentation) {
        mediaType = 'application/octet-stream';
    } else if (segmentation instanceof MaskedSegmentation) {
        mediaType = 'application/json';
    }

    // create annotationData if it does not exist
    if (!annotationData) {
        console.log('creating', annotation, scanNr, mediaType);
        annotationData = await data.annotationDatas.create({ annotation, scanNr, mediaType });
    }
    return annotationData;
}

export async function updateServer(segmentation: Segmentation, scanNr: number): Promise<HTMLCanvasElement> {
    // updates server with correct value (according to media type)
    // returns canvas with updated value

    const annotationData = await getAnnotationData(segmentation, scanNr);
    const image = segmentation.image;
    const ctx = image.getDrawingCtx();

    // renders current state to ctx
    segmentation.export(scanNr, ctx);

    let serverValue;
    switch (annotationData.mediaType) {
        case 'image/png':
            serverValue = ctx.canvas;
            break;

        case 'application/json':
            if (segmentation instanceof MaskedSegmentation) {
                // update branch with current drawing
                segmentation.branch.drawing = ctx.canvas.toDataURL();
                // same as current value, the object is mutated
                serverValue = annotationData.value.value
            } else {
                console.error('Unsupported combination segmentation / media type', annotationData.mediaType);
            }
            break;

        case 'application/octet-stream':
            if (segmentation instanceof MulticlassSegmentation) {
                serverValue = segmentation.data.getBscan(scanNr);
            } else if (segmentation instanceof MultilabelSegmentation) {
                serverValue = segmentation.data.getBscan(scanNr);
            } else {
                console.error('Unsupported combination segmentation / media type', annotationData.mediaType);
            }
            break;

        default:
            console.error('Unsupported media type', annotationData.mediaType);
            break;
    }
    if (serverValue) {
        await annotationData.value.setValue(serverValue);
    }
    return ctx.canvas;
}
