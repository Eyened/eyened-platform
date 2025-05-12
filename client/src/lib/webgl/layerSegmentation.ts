import type { Annotation } from "$lib/datamodel/annotation";
import type { AnnotationData } from "$lib/datamodel/annotationData";
import { featureLabels } from "$lib/viewer-window/panelSegmentation/segmentationUtils";
import type { Segmentation } from "./SegmentationController";
import type { AbstractImage } from "./abstractImage";
import { LayerBoundaries } from "./layerBoundaries";
import { CanvasToUint16Array, CanvasToUint8Array, MulticlassData, MultilabelData, Uint16ArrayToCanvas, Uint8ArrayToCanvasGray as Uint8ArrayToCanvasGray } from "./segmentationData";

abstract class BaseSegmentation implements Segmentation {
    public readonly dataInterpretation: { [layerName: string]: number };
    abstract questionable_bit: number;

    constructor(
        public readonly id: string,
        public readonly image: AbstractImage,
        public readonly annotation: Annotation,
    ) {
        this.dataInterpretation = featureLabels[annotation.feature.name];
    }

    abstract get data(): MulticlassData | MultilabelData;
    abstract dispose(): void;
    abstract draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void;
    abstract clear(scanNr: number): void;
    abstract export(scanNr: number, ctx: CanvasRenderingContext2D): void;
    abstract import(scanNr: number, canvas: HTMLCanvasElement): void;
    abstract importBscanFromArrayBuffer(scanNr: number, data: ArrayBuffer): void;
    abstract importVolumeFromArrayBuffer(data: ArrayBuffer): void;
    abstract importOther(scanNr: number, other: Segmentation): void;

    protected getNeighbors(i: number): number[] {
        // returns the indices of the neighbors of pixel i
        const { width, height } = this.image;
        const neighbors = [];
        const x = i % width;
        const y = Math.floor(i / width);
        if (x > 0) {
            neighbors.push(i - 1);
        }
        if (x < width - 1) {
            neighbors.push(i + 1);
        }
        if (y > 0) {
            neighbors.push(i - width);
        }
        if (y < height - 1) {
            neighbors.push(i + width);
        }
        return neighbors;
    }

    protected drawQuestionable(data: Uint8Array | Uint16Array, i: number, isPaint: boolean): void {
        if (isPaint) { // add questionable bit
            data[i] |= this.questionable_bit;
        } else { // remove questionable bit
            data[i] &= ~this.questionable_bit;
        }
    }

    protected getDrawingContext(drawing: HTMLCanvasElement): { ctx: CanvasRenderingContext2D, drawingData: ImageData, drawingArray: Uint8ClampedArray } {
        const { width, height } = this.image;
        const ctx = drawing.getContext('2d')!;
        const drawingData = ctx.getImageData(0, 0, width, height);
        const drawingArray = drawingData.data;
        return { ctx, drawingData, drawingArray };
    }

    initialize(annotationData: AnnotationData, dataRaw: any): void {
        function getBuffer(): ArrayBuffer {
            if (dataRaw instanceof ArrayBuffer) {
                return dataRaw;
            } else if (dataRaw instanceof Uint8Array || dataRaw instanceof Uint16Array) {
                return dataRaw.buffer as ArrayBuffer;
            } else if (dataRaw instanceof HTMLCanvasElement) {
                const array = CanvasToUint8Array(dataRaw);
                return array.buffer as ArrayBuffer;
            } else {
                throw new Error('Unsupported data type');
            }
        }
        const buffer = getBuffer();

        const annotationType = this.annotation.annotationType.name;
        if (annotationType === 'Segmentation OCT Volume') {
            this.importVolumeFromArrayBuffer(buffer);
        } else if (annotationType === 'Segmentation OCT B-scan') {
            this.importBscanFromArrayBuffer(annotationData.scanNr, buffer);
        } else {
            throw new Error('Unsupported data type');
        }
    }
}

export class MulticlassSegmentation extends BaseSegmentation {
    public data: MulticlassData;
    public questionable_bit: number = 1 << 7;

    private _layerBoundaries: LayerBoundaries;
    private layerBoundariesValid: boolean = false;

    constructor(id: string, image: AbstractImage, annotation: Annotation) {
        super(id, image, annotation);
        this.data = new MulticlassData(image);
        this._layerBoundaries = new LayerBoundaries(image, this.data.texture);
    }

    get layerBoundaries(): LayerBoundaries {
        if (!this.layerBoundariesValid) {
            console.log('calculateBoundaries')
            this._layerBoundaries.calculateBoundaries();
            this.layerBoundariesValid = true;
        }
        return this._layerBoundaries;
    }

    dispose(): void {
        this.data.dispose();
    }

    getLabelNumber(selectedLabelNames: string | string[]): number {
        // this data type only support drawing one label at a time
        if (Array.isArray(selectedLabelNames)) {
            console.warn('Array of labels not supported', selectedLabelNames);
            return 0;
        }

        try {
            return this.dataInterpretation[selectedLabelNames];
        } catch (error) {
            console.warn('Label not found in dataInterpretation', selectedLabelNames);
        }
        return 0;
    }

    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void {
        const current = this.data.getBscan(scanNr);
        // need to make a copy, because it's modified in the loop        
        const data = new Uint8Array(current);

        const { drawingArray } = this.getDrawingContext(drawing);
        const number = this.getLabelNumber(settings.selectedLabelNames);
        const isPaint = settings.mode == 'paint';
        const isQuestionable = settings.questionable;
        const isErodeDilate = settings.erodeDilate;

        const drawErodeDilate = (i: number) => {
            if (isPaint) { // update to selected label
                if (isErodeDilate) {
                    for (const n of this.getNeighbors(i)) {
                        if (current[n] == number) {
                            data[i] = number;
                            break;
                        }
                    }
                } else {
                    data[i] = number;
                }
            } else if (data[i] == number) { // only erase if the label is the same                        
                if (isErodeDilate) {
                    for (const n of this.getNeighbors(i)) {
                        if (current[n] != number) {
                            // update to value of neighbor
                            data[i] = data[n];
                            break;
                        }
                    }
                } else {
                    data[i] = 0;
                }
            }
        }

        for (let i = 0; i < this.image.width * this.image.height; i++) {
            // if the pixel is painted
            if (drawingArray[i * 4] > 0) {
                if (isQuestionable) {
                    this.drawQuestionable(data, i, isPaint);
                } else {
                    drawErodeDilate(i);
                }
            }
        }
        this.updateBscan(scanNr, data);
    }

    clear(scanNr: number): void {
        this.updateBscan(scanNr, new Uint8Array(this.image.width * this.image.height));
    }

    private updateBscan(scanNr: number, data: Uint8Array): void {
        // also updates gpu data
        this.data.setBscan(scanNr, data);
        this.after_update();
    }

    after_update() {
        this.layerBoundariesValid = false
    }

    import(scanNr: number, canvas: HTMLCanvasElement): void {
        this.updateBscan(scanNr, CanvasToUint8Array(canvas));
    }

    importBscanFromArrayBuffer(scanNr: number, data: ArrayBuffer): void {
        this.updateBscan(scanNr, new Uint8Array(data));
    }

    importVolumeFromArrayBuffer(data: ArrayBuffer): void {
        this.data.setVolume(new Uint8Array(data));
        this.after_update();
    }

    importOther(scanNr: number, other: Segmentation): void {
        if (other instanceof MulticlassSegmentation) {
            // TODO: what if the other segmentation has different labels (dataInterpretation)?
            this.updateBscan(scanNr, other.data.getBscan(scanNr));
        } else if (other instanceof MultilabelSegmentation) {
            const other_data = other.data.getBscan(scanNr);
            const data = new Uint8Array(this.image.width * this.image.height);
            for (let i = 0; i < data.length; i++) {
                const value = other_data[i];
                if (value > 0) {
                    // convert layer bit to label number
                    data[i] = Math.log2(value) + 1;
                }
            }
            this.updateBscan(scanNr, data);
        } else {
            throw new Error("Unsupported segmentation type");
        }
    }

    export(scanNr: number, ctx: CanvasRenderingContext2D): void {
        const data = this.data.getBscan(scanNr);
        Uint8ArrayToCanvasGray(data, ctx);
    }
}

export class MultilabelSegmentation extends BaseSegmentation {
    public data: MultilabelData;
    public questionable_bit: number = 1 << 15;

    constructor(id: string, image: AbstractImage, annotation: Annotation) {
        super(id, image, annotation);
        this.data = new MultilabelData(image);
    }

    dispose(): void {
        this.data.dispose();
    }

    getBitmask(selectedLabelNames: string[]): number {
        let bitmask = 0;
        for (const labelName of selectedLabelNames) {
            const i = this.dataInterpretation[labelName];
            if (i) {
                bitmask |= 1 << (i - 1);
            }
        }
        return bitmask;
    }

    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void {
        const bitmask = this.getBitmask(settings.selectedLabelNames);
        const data = this.data.getBscan(scanNr);
        const { drawingArray } = this.getDrawingContext(drawing);

        const isPaint = settings.mode == 'paint';
        const isQuestionable = settings.questionable;
        // TODO: implement erosion and dilation

        for (let i = 0; i < this.image.width * this.image.height; i++) {
            if (drawingArray[i * 4] > 0) {
                if (isQuestionable) {
                    this.drawQuestionable(data, i, isPaint);
                } else {
                    // drawing adds the bitmask, leaving other bits unchanged
                    if (isPaint) {
                        data[i] |= bitmask;
                    } else {
                        // erasing removes the bitmask, leaving other bits unchanged
                        data[i] &= ~bitmask;
                    }
                }
            }
        }
        // also updates gpu data 
        this.data.setBscan(scanNr, data);
    }

    clear(scanNr: number): void {
        this.data.setBscan(scanNr, new Uint16Array(this.image.width * this.image.height));
    }

    export(scanNr: number, ctx: CanvasRenderingContext2D): void {
        const data = this.data.getBscan(scanNr);
        Uint16ArrayToCanvas(data, ctx);
    }

    import(scanNr: number, canvas: HTMLCanvasElement): void {
        this.data.setBscan(scanNr, CanvasToUint16Array(canvas));
    }

    importBscanFromArrayBuffer(scanNr: number, data: ArrayBuffer): void {
        this.data.setBscan(scanNr, new Uint16Array(data));
    }

    importVolumeFromArrayBuffer(data: ArrayBuffer): void {
        this.data.setVolume(new Uint16Array(data));
    }

    importOther(scanNr: number, other: Segmentation): void {
        if (other instanceof MultilabelSegmentation) {
            // TODO: what if the other segmentation has different labels (dataInterpretation)?
            this.data.setBscan(scanNr, other.data.getBscan(scanNr));
        } else if (other instanceof MulticlassSegmentation) {
            const other_data = other.data.getBscan(scanNr);
            const data = new Uint16Array(this.image.width * this.image.height);
            for (let i = 0; i < data.length; i++) {
                const value = other_data[i];
                if (value > 0) {
                    // convert label number to layer bit
                    if (0 < value && value < 16) {
                        data[i] = 1 << (value - 1);
                    }
                }
            }
            this.data.setBscan(scanNr, data);
        } else {
            throw new Error("Unsupported segmentation type");
        }
    }
}
