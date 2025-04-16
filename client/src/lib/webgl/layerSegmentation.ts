import type { Annotation } from "$lib/datamodel/annotation";
import { featureLabels } from "$lib/viewer-window/panelSegmentation/segmentationUtils";
import type { Segmentation } from "./SegmentationController";
import type { AbstractImage } from "./abstractImage";
import { LayerBoundaries } from "./layerBoundaries";
import { CanvasToUint16Array, CanvasToUint8Array, LabelNumbersData, LayerBitData, Uint16ArrayToCanvas, Uint8ArrayToCanvasGray as Uint8ArrayToCanvasGray } from "./segmentationData";

export class LabelNumbersSegmentation implements Segmentation {

    public data: LabelNumbersData;
    public readonly dataInterpretation: { [layerName: string]: number };
    public questionable_bit: number = 1 << 7;

    private _layerBoundaries: LayerBoundaries;
    private layerBoundariesValid: boolean = false;

    constructor(public readonly id: string,
        public readonly image: AbstractImage,
        public readonly annotation: Annotation,
    ) {
        this.data = new LabelNumbersData(image);
        this.dataInterpretation = featureLabels[annotation.feature.name];
        this._layerBoundaries = new LayerBoundaries(image, this.data.texture);
    }

    get layerBoundaries(): LayerBoundaries {
        if (!this.layerBoundariesValid) {
            this._layerBoundaries.calculateBoundaries();
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

    private getNeighbors(i: number): number[] {
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


    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void {

        const current = this.data.getBscan(scanNr);
        // need to make a copy, because it's modified in the loop        
        const data = new Uint8Array(current);

        const { width, height } = this.image;
        const ctx = drawing.getContext('2d')!;
        const drawingData = ctx.getImageData(0, 0, width, height);
        const drawingArray = drawingData.data;
        const number = this.getLabelNumber(settings.selectedLabelNames);
        const isPaint = settings.mode == 'paint';
        const isQuestionable = settings.questionable;
        const isErodeDilate = settings.erodeDilate;

        const drawQuestionable = (i: number) => {
            if (isPaint) { // add questionable bit
                data[i] |= this.questionable_bit;
            } else { // remove questionable bit
                data[i] &= ~this.questionable_bit;
            }
        }
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
        for (let i = 0; i < width * height; i++) {
            // if the pixel is painted
            if (drawingArray[i * 4] > 0) {
                if (isQuestionable) {
                    drawQuestionable(i);
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
        if (other instanceof LabelNumbersSegmentation) {
            // TODO: what if the other segmentation has different labels (dataInterpretation)?
            this.updateBscan(scanNr, other.data.getBscan(scanNr));
        } else if (other instanceof LayerBitsSegmentation) {

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

export class LayerBitsSegmentation implements Segmentation {

    public data: LayerBitData;
    public readonly dataInterpretation: { [layerName: string]: number };
    public questionable_bit: number = 1 << 15;

    constructor(public readonly id: string,
        public readonly image: AbstractImage,
        public readonly annotation: Annotation
    ) {
        this.data = new LayerBitData(image);
        this.dataInterpretation = featureLabels[annotation.feature.name];
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
        const { width, height } = this.image;
        const ctx = drawing.getContext('2d')!;
        const drawingData = ctx.getImageData(0, 0, width, height);
        const drawingArray = drawingData.data;

        const isPaint = settings.mode == 'paint';
        const isQuestionable = settings.questionable;
        // TODO: implement questionable
        // TODO: implement erosion and dilation

        for (let i = 0; i < width * height; i++) {
            if (drawingArray[i * 4] > 0) {
                if (isQuestionable) {
                    if (isPaint) { // add questionable bit
                        data[i] |= this.questionable_bit;
                    } else { // remove questionable bit
                        data[i] &= ~this.questionable_bit;
                    }
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
        if (other instanceof LayerBitsSegmentation) {
            // TODO: what if the other segmentation has different labels (dataInterpretation)?
            this.data.setBscan(scanNr, other.data.getBscan(scanNr));
        } else if (other instanceof LabelNumbersSegmentation) {

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
