// import { getImage } from "$lib/data-loading/imageLoader";
import type { Annotation } from "$lib/datamodel/annotation.svelte";
import type { AnnotationData, AnnotationPlane } from "$lib/datamodel/annotationData.svelte";
import type { DataRepresentation } from "$lib/datamodel/annotationType";
import { BlobExtraction } from "$lib/image-processing/connected-component-labelling";
import type { Branch } from "$lib/types";
import { BaseSegmentation, type Segmentation } from "./baseSegmentation";
import type { AbstractImage } from "./abstractImage";
import { RenderTexture, type TextureDataFormat } from "./renderTexture";
import type { SharedData } from "./segmentationData";
import { SvelteMap } from "svelte/reactivity";

export class BinarySegmentation extends BaseSegmentation {

    // bitmask for this segmentation (1 << layerIndex)
    public readonly layerBit: number;

    // maps scanNr to the number of pixels in the segmentation
    pixelArea = new SvelteMap<number, number>();

    // stores a single texture for the entire segmentation
    // will be invalidated if the segmentation is modified
    // lazily computed when needed
    private connectedComponents: WebGLTexture | undefined;
    private connectedComponentsValid: false | number = false;

    private dataRepresentation = 'BINARY';

    /**
     * 
     * @param id: unique identifier (implemented as string of annotation.id)
     * @param image: the image that is being annotated
     * @param annotation: Annotation with interpretation 'Binary mask' or 'R/G mask'
     * @param data: SharedDataRG (R = segmentation mask, G = questionable mask)
     * @param layerIndex: index of the layer in the SharedDataRG
     */
    constructor(
        readonly id: string,
        readonly image: AbstractImage,
        readonly annotation: Annotation,
        readonly data: SharedData,
        readonly layerIndex: number,
        readonly annotationPlane: AnnotationPlane
    ) {
        super(id, image, annotation, annotationPlane);
        this.layerBit = 1 << layerIndex        
    }

    initialize(annotationData: AnnotationData, dataRaw: any): void {
        if (dataRaw instanceof HTMLCanvasElement || dataRaw instanceof WebGLTexture || dataRaw instanceof ImageBitmap) {
            this.import(annotationData.scanNr, dataRaw);
        } else if (dataRaw instanceof ArrayBuffer) {
            this.initializeArrayBuffer(annotationData, dataRaw);
        } else {
            console.warn('Unsupported data type', dataRaw);
            throw new Error('Unsupported data type');
        }
    }


    initializeArrayBuffer(annotationData: AnnotationData, dataRaw: ArrayBuffer): void {
        const { width, height, depth } = this;

        const renderTexture = new RenderTexture(this.webgl, width, height, 'R8UI', null);

        if (annotationData.annotationPlane === "VOLUME") {
            const size = width * height;
            for (let i = 0; i < depth; i++) {
                const data = new Uint8Array(dataRaw.slice(i * size, (i + 1) * size));
                renderTexture.setDataArray(data);
                this.import(i, renderTexture.texture, 0.0);
            }
        } else {
            const data = new Uint8Array(dataRaw);
            renderTexture.setDataArray(data);
            this.import(annotationData.scanNr, renderTexture.texture, 0.0);
        }
        renderTexture.dispose();
    }

    /**
     * Modify the segmentation using the image in the canvas
     * 
     * use settings.mode = 'paint' or 'erase' to draw or erase
     * use settings.questionable = true to draw to the questionable mask (G in R/G mask)
     * use settings.erodeDilate = true to erode/dilate instead of erase/draw
     * 
     * @param scanNr: B-scan number
     * @param drawing: HTMLCanvasElement (checking red channel: 0 = background, >0 = drawing / erasing)
     * @param settings: { mode: 'paint' | 'erase', questionable: boolean, erodeDilate: boolean }
     */
    draw(scanNr: number, drawing: HTMLCanvasElement, settings: any): void {

        const uniforms = {
            u_bitmask: this.layerBit,
            u_current: this.data.getTexture(scanNr),
            u_drawing: this.image.getTextureForCanvas(drawing),
            u_questionable: settings.questionable,
            u_paint: settings.mode == 'paint'
        };

        if (settings.erodeDilate) {
            this.data.passShader(scanNr, this.shaders.erodeDilate, uniforms);
        } else {
            this.data.passShader(scanNr, this.shaders.draw, uniforms);
        }
        this._after_update(scanNr);
    }

    /**
     * Clear the segmentation
     * @param scanNr 
     */
    clear(scanNr: number): void {
        const uniforms = {
            u_current: this.data.getTexture(scanNr),
            u_bitmask: this.layerBit
        };
        this.data.passShader(scanNr, this.shaders.clear, uniforms);
        this._after_update(scanNr);
    }

    /**
     * Import the segmentation from the canvas
     * The red channel is used for the actual segmentation, the green channel for the questionable mask
     * Only reads the green channel if the annotation is RG_MASK
     * 
     * @param scanNr 
     * @param canvas R/G mask
     */
    import(scanNr: number, canvas: HTMLCanvasElement | WebGLTexture | ImageBitmap, u_threshold: number = 0.5): void {
        let u_drawing: WebGLTexture;
        if (canvas instanceof HTMLCanvasElement || canvas instanceof ImageBitmap) {
            u_drawing = this.image.getTextureForCanvas(canvas);
        } else {
            u_drawing = canvas;
        }
        // Annotations with binary data are stored as single channel (black/white) images.
        // However the canvas is always 4 channels, so the green channel will also be set.
        // This should not be interpreted as the 'questionable' mask        
        const u_has_questionable_mask = this.annotation.annotationType.dataRepresentation == 'RG_MASK';

        const uniforms = {
            u_current: this.data.getTexture(scanNr),
            u_drawing,
            u_bitmask: this.layerBit,
            u_has_questionable_mask,
            u_threshold
        };
        this.data.passShader(scanNr, this.shaders.import, uniforms);
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
        // export the other segmentation to ctx, using the dataRepresentation of the current annotation
        other.export(scanNr, ctx, this.dataRepresentation);
        this.import(scanNr, ctx.canvas);
    }

    /**
     * Export the segmentation to the canvas associated with the context
     * For BINARY: Creates a black/white image (R=G=B=255 for annotation)
     * For RG_MASK: Creates an RGB image (R=255 for annotation, G=255 for questionable, B=0)
     * @param scanNr 
     * @param ctx 
     * @param dataRepresentation if omitted, uses the dataRepresentation of the annotation
     */
    export(scanNr: number, ctx: CanvasRenderingContext2D, dataRepresentation?: DataRepresentation): void {
        // CPU-side implementation, not meant for real-time rendering

        const data = this.data.getBscan(scanNr);
        const { width, height } = this;
        const imageData = ctx.getImageData(0, 0, width, height);
        const dataOut = imageData.data;
        const isRGMask = (dataRepresentation || this.dataRepresentation) === 'RG_MASK';

        for (let i = 0; i < width * height; i++) {
            const dataIndex = 2 * i;
            const dataOutIndex = 4 * i;
            const hasAnnotation = data[dataIndex] & this.layerBit;
            const hasQuestionable = data[dataIndex + 1] & this.layerBit;

            if (hasAnnotation) {
                dataOut[dataOutIndex] = 255;     // R = 255 for annotation
                if (!isRGMask) {
                    // BINARY: Set all channels to 255                    
                    dataOut[dataOutIndex + 1] = 255; // G
                    dataOut[dataOutIndex + 2] = 255; // B
                }
            }

            if (isRGMask && hasQuestionable) {
                dataOut[dataOutIndex + 1] = 255;     // G = 255 for questionable
            }

            dataOut[dataOutIndex + 3] = 255;         // Alpha = 255
        }
        ctx.putImageData(imageData, 0, 0);
    }

    getData(scanNr: number): Uint8Array {
        return this.data.getBscan(scanNr);
    }

    dispose(): void {
        for (let i = 0; i < this.depth; i++) {
            this.clear(i);
        }
        if (this.connectedComponents !== undefined) {
            this.webgl.gl.deleteTexture(this.connectedComponents);
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
        // data is a Uint8Array with 2 bytes per pixel (R and G)
        const data = this.data.getBscan(scanNr);
        const { width, height } = this;
        const binaryArray = new Uint8Array(width * height);
        for (let i = 0; i < binaryArray.length; i++) {
            // note 2 * i to skip the green channel (only R is used)
            binaryArray[i] = data[2 * i] & this.layerBit;
        }
        const label = BlobExtraction(binaryArray, width, height);
        // label contains the connected components (0 = background, 1 = first component, 2 = second component, ...)

        // upload to texture
        const gl = this.webgl.gl;
        gl.bindTexture(gl.TEXTURE_2D, this.connectedComponents!);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, width, height, 0, gl.RED_INTEGER, gl.UNSIGNED_BYTE, label);

        this.connectedComponentsValid = scanNr;
    }


    countPixels(scanNr: number): number {
        const data = this.data.getBscan(scanNr);
        let count = 0;
        // note: i += 2 to skip the green channel (only R is used)
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
        data: SharedData,
        layerIndex: number,
        public readonly maskSegmentation: BinarySegmentation,
        public readonly branch: Branch
    ) {
        super(id, image, annotation, data, layerIndex);
    }

    initialize(annotationData: AnnotationData, dataRaw: any): void {
        try {
            const { branches } = dataRaw;
            for (const branch of branches as Branch[]) {
                if (branch == this.branch) {
                    getImage(branch.drawing).then(canvas => this.import(annotationData.scanNr, canvas));
                }
            }
        } catch (error) {
            console.warn('Unsupported data type', dataRaw);
            throw new Error('Unsupported data type');
        }
    }
}