import type { Annotation } from "$lib/datamodel/annotation";
import { BlobExtraction } from "$lib/image-processing/connected-component-labelling";
import type { Branch } from "$lib/types";
import type { Segmentation } from "./SegmentationController";
import type { AbstractImage } from "./abstractImage";
import type { ProbabilitySegmentation } from "./probabilitySegmentation.svelte";
import type { SharedDataRG } from "./segmentationData";
import { SvelteMap } from "svelte/reactivity";

export class BinarySegmentation implements Segmentation {

    // mask (bitmask) for this segmentation
    public readonly layerBit: number;

    // maps scanNr to the number of pixels in the segmentation
    pixelArea = new SvelteMap<number, number>();

    // stores a single texture for the entire segmentation
    // will be invalidated if the segmentation is modified
    // lazily computed when needed
    private connectedComponents: WebGLTexture | undefined;
    private connectedComponentsValid: false | number = false;


    constructor(
        readonly id: string,
        readonly image: AbstractImage,
        readonly annotation: Annotation,
        readonly data: SharedDataRG,
        readonly layerIndex: number
    ) {
        this.layerBit = 1 << layerIndex;
    }

    /**
     * Draw or erase using the image in the canvas
     * The red channel is used for drawing, the green channel for erasing
     * 
     * @param scanNr 
     * @param drawing 
     * @param settings { questionable: boolean, erodeDilate: boolean }
     */
    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void {
        const { webgl: { shaders } } = this.image;

        const uniforms = {
            u_bitmask: this.layerBit,
            u_current: this.data.getTexture(scanNr),
            u_drawing: this.image.getTextureForCanvas(drawing),
            u_questionable: settings.questionable,
            u_paint: settings.mode == 'paint'
        };

        if (settings.erodeDilate) {
            this.data.passShader(scanNr, shaders.erodeDilate, uniforms);
        } else {
            this.data.passShader(scanNr, shaders.draw, uniforms);
        }
        this._after_update(scanNr);
    }

    /**
     * Clear the segmentation
     * @param scanNr 
     */
    clear(scanNr: number): void {
        const { webgl: { shaders } } = this.image;
        const uniforms = {
            u_current: this.data.getTexture(scanNr),
            u_bitmask: this.layerBit
        };
        this.data.passShader(scanNr, shaders.clear, uniforms);
        this._after_update(scanNr);
    }

    /**
     * Import the segmentation from the canvas
     * The red channel is used for the actual segmentation, the green channel for the questionable mask
     * Only reads the green channel if the annotation interpretation is 'R/G mask'
     * 
     * @param scanNr 
     * @param canvas R/G mask
     */
    import(scanNr: number, canvas: HTMLCanvasElement): void {
        const { webgl: { shaders } } = this.image;

        // Annotations with binary data are stored as single channel (black/white) images.
        // However the canvas is always 4 channels, so the green channel will also be set.
        // This should not be interpreted as the 'questionable' mask        
        const u_has_questionable_mask = this.annotation.interpretation == 'R/G mask';

        const uniforms = {
            u_current: this.data.getTexture(scanNr),
            u_drawing: this.image.getTextureForCanvas(canvas),
            u_bitmask: this.layerBit,
            u_has_questionable_mask
        };
        this.data.passShader(scanNr, shaders.import, uniforms);
        this._after_update(scanNr);
    }

    _after_update(scanNr: number) {
        // called after import / draw / clear
        this.connectedComponentsValid = false;
        this.pixelArea.set(scanNr, this.countPixels(scanNr));
    }

    /**
     * Import from another segmentation
     * Replaces the current segmentation with the other segmentation
     * 
     * @param scanNr 
     * @param other 
     */
    importOther(scanNr: number, other: Segmentation): void {
        const ctx = this.image.getIOCtx();
        other.export(scanNr, ctx);

        // TODO: this conversion should probably be moved to the export function
        if (this.annotation.interpretation === 'R/G mask') {
            const otherInterpretation = other.annotation.interpretation
            if (otherInterpretation === 'Binary mask') {
                // other has no questionable mask, remove the green channel
                const imageData = ctx.getImageData(0, 0, this.image.width, this.image.height);
                const data = imageData.data;
                for (let i = 0; i < data.length; i++) {
                    data[4 * i + 1] = 0;
                }
                ctx.putImageData(imageData, 0, 0);
            }
            if (otherInterpretation === 'Probability') {
                // apply threshold (should be moved to ProbabilitySegmentation?)
                const imageData = ctx.getImageData(0, 0, this.image.width, this.image.height);
                const data = imageData.data;
                const th = (other as ProbabilitySegmentation).threshold * 255;
                for (let i = 0; i < data.length; i++) {
                    if (data[4 * i] < th) {
                        data[4 * i] = 0;
                    }
                    // remove green channel (probability segmentation is exported to gray canvas)
                    data[4 * i + 1] = 0;
                }
                ctx.putImageData(imageData, 0, 0);

            }
        }
        this.import(scanNr, ctx.canvas);
    }

    /**
     * Export the segmentation to the canvas associated with the context
     * The output uses the red channel for the actual segmentation, the green channel for the questionable mask
     * Only writes the green channel if the annotation interpretation is 'R/G mask'
     * 
     * TODO: probably better to have different export functions for different interpretations
     * 
     * @param scanNr 
     * @param ctx 
     */
    export(scanNr: number, ctx: CanvasRenderingContext2D): void {
        // CPU-side implementation, not meant for real-time rendering

        const data = this.data.getBscan(scanNr);
        const { width, height } = this.image;
        const length = width * height;
        const imageData = ctx.getImageData(0, 0, width, height);
        const dataOut = imageData.data;

        const isRGMask = this.annotation.interpretation === 'R/G mask';

        for (let i = 0; i < length; i++) {
            const dataIndex = 2 * i;
            const dataOutIndex = 4 * i;

            if (data[dataIndex] & this.layerBit) {
                dataOut[dataOutIndex] = 255; // red
            }

            if (isRGMask) {
                if (data[dataIndex + 1] & this.layerBit) {
                    dataOut[dataOutIndex + 1] = 255; // green
                }
            } else {
                dataOut[dataOutIndex + 1] = 255; // green
                dataOut[dataOutIndex + 2] = 255; // blue
            }
            dataOut[dataOutIndex + 3] = 255; // alpha
        }
        ctx.putImageData(imageData, 0, 0);
    }

    dispose(): void {
        for (let i = 0; i < this.image.depth; i++) {
            this.clear(i);
        }
        if (this.connectedComponents !== undefined) {
            this.image.webgl.gl.deleteTexture(this.connectedComponents);
        }
    }


    getConnectedComponents(scanNr: number) {
        if (this.connectedComponents === undefined) {
            this.connectedComponents = this.image.createTextureR8UI();
        }
        if (this.connectedComponentsValid !== scanNr) {
            this.computeConnectedComponents(scanNr);
        }
        return this.connectedComponents;
    }

    computeConnectedComponents(scanNr: number) {
        const data = this.data.getBscan(scanNr);
        const { width, height } = this.image;
        const binaryArray = new Uint8Array(width * height);
        for (let i = 0; i < binaryArray.length; i++) {
            binaryArray[i] = data[2 * i] & this.layerBit;
        }
        const label = BlobExtraction(binaryArray, this.image.width, this.image.height);
        // label contains the connected components (0 = background, 1 = first component, 2 = second component, ...)

        // upload to texture
        const gl = this.image.webgl.gl;
        gl.bindTexture(gl.TEXTURE_2D, this.connectedComponents!);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, this.image.width, this.image.height, 0, gl.RED_INTEGER, gl.UNSIGNED_BYTE, label);

        this.connectedComponentsValid = scanNr;
    }


    countPixels(scanNr: number): number {
        const data = this.data.getBscan(scanNr);
        let count = 0;
        for (let i = 0; i < data.length; i += 2) {
            if (data[i] & this.layerBit) {
                count++;
            }
        }
        return count;
    }

}

export class MaskedSegmentation extends BinarySegmentation {
    constructor(
        id: string,
        image: AbstractImage,
        annotation: Annotation,
        data: SharedDataRG,
        layerIndex: number,
        public readonly maskSegmentation: BinarySegmentation,
        public readonly branch: Branch
    ) {
        super(id, image, annotation, data, layerIndex);
    }
}