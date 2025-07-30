import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";
import { AbstractImage } from "./abstractImage";
import type { Instance } from "$lib/datamodel/instance.svelte";
import type { RenderMode } from "$lib/viewer/viewer-utils";
import { TextureData } from "./texture";

// Define metadata interface
interface ImageMetadata {
    [key: string]: unknown;
}

export class Image2D extends AbstractImage {
    is3D = false;
    is2D = true;
    contrastEnhanced!: TextureData;
    sharpened!: TextureData;
    CLAHE!: TextureData;
    standardizedMuSigma!: TextureData;
    standardizedHistogram!: TextureData;

    constructor(
        instance: Instance,
        webgl: WebGL,
        image_id: string,
        readonly textureData: TextureData,
        dimensions: Dimensions,
        meta: ImageMetadata
    ) {
        super(instance, webgl, image_id, dimensions, meta);
    }

    get texture(): WebGLTexture {
        return this.textureData.texture;
    }

    private async initialize() {
        const { cfImageProcessing } = this.webgl;
        const { contrastEnhanced, sharpened, clahe, muSigma, hist } = await cfImageProcessing.preprocessAll(this);
        this.contrastEnhanced = contrastEnhanced;
        this.sharpened = sharpened;
        this.CLAHE = clahe || this.textureData;
        this.standardizedMuSigma = muSigma;
        this.standardizedHistogram = hist;
    }

    static fromBitmap(instance: Instance, webgl: WebGL, image_id: string, bitmap: ImageBitmap, dimensions: Dimensions, meta: any) {
        const texture = initTexture(webgl.gl, bitmap);
        const result = new Image2D(instance, webgl, image_id, texture, dimensions, meta);
        result.initialize();
        return result;
    }

    /**
     * Create an Image2D from a pixel data array.
     * @param instance 
     * @param webgl 
     * @param image_id 
     * @param pixelData Can be 1, 2, 3, or 4 channels. 1D array of length width * height * num_channels.
     * @param dimensions 
     * @param meta 
     * @returns 
     */
    static fromPixelData(instance: Instance, webgl: WebGL, image_id: string, pixelData: Uint8Array, dimensions: Dimensions, meta: any) {
        const texture = new TextureData(webgl.gl, dimensions.width, dimensions.height, 'RGBA');

        let data;
        const source_num_channels = pixelData.length / (dimensions.width * dimensions.height);
        if (source_num_channels === 4) {
            data = pixelData;
        } else if (source_num_channels === 1 || source_num_channels === 2 || source_num_channels === 3) {
            data = new Uint8Array(dimensions.width * dimensions.height * 4);
            for (let i = 0; i < dimensions.width * dimensions.height; i++) {
                for (let c = 0; c < source_num_channels; c++) {
                    data[4 * i + c] = pixelData[source_num_channels * i + c];
                }
                data[4 * i + 3] = 255;
            }
        } else {
            throw new Error(`Unsupported number of channels: ${source_num_channels}`);
        }

        texture.uploadData(data);

        const result = new Image2D(instance, webgl, image_id, texture, dimensions, meta);
        result.initialize();
        return result;
    }

    get pixels_rgba() {
        return this.textureData.data;
    }

    selectTexture(renderMode: RenderMode) {
        const textureMap = {
            "Contrast enhanced": this.contrastEnhanced?.texture,
            "Color balanced": this.standardizedMuSigma?.texture,
            "CLAHE": this.CLAHE?.texture || this.texture,
            "Sharpened": this.sharpened?.texture,
            "Histogram matched": this.standardizedHistogram?.texture,
            "Original": this.texture
        };

        return textureMap[renderMode] || this.texture;
    }
}

function initTexture(gl: WebGL2RenderingContext, canvas: HTMLCanvasElement | ImageBitmap): TextureData {
    const texture = new TextureData(gl, canvas.width, canvas.height, 'RGBA');
    texture.uploadCanvas(canvas);
    return texture;
}

function isImageGrayscale(canvas: HTMLCanvasElement): boolean {
    const ctx = canvas.getContext('2d', { willReadFrequently: true })!;

    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;

    for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];

        if (r !== g || g !== b) {
            return false;
        }
    }

    return true;
}

function getCanvas(pixelData: Uint8Array, width: number, height: number): HTMLCanvasElement {
    const nChannels = pixelData.length / (width * height);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;

    // Get the 2D context of the canvas
    const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
    const imageData = ctx.getImageData(0, 0, width, height);
    const n = width * height;
    if (nChannels === 1) {
        for (let i = 0; i < n; i++) {
            for (let c = 0; c < 3; c++) {
                imageData.data[4 * i + c] = pixelData[i];
            }
            imageData.data[4 * i + 3] = 255;
        }
    } else {
        for (let i = 0; i < n; i++) {
            for (let c = 0; c < nChannels; c++) {
                imageData.data[4 * i + c] = pixelData[nChannels * i + c];
            }
            if (nChannels < 4) {
                imageData.data[4 * i + 3] = 255;
            }
        }
    }
    ctx.putImageData(imageData, 0, 0);
    return canvas;
}