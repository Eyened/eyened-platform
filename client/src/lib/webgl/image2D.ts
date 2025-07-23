import type { Dimensions } from "./types";
import type { WebGL } from "./webgl";
import { colorStandardization } from "$lib/image-processing/color-standardization";

import { AbstractImage } from "./abstractImage";
import type { RenderTexture } from "./renderTexture";
import type { Instance } from "$lib/datamodel/instance.svelte";
import type { RenderMode } from "$lib/viewer/viewer-utils";

// Define metadata interface
interface ImageMetadata {
    [key: string]: unknown;
}

export class Image2D extends AbstractImage {
    is3D = false;
    is2D = true;
    contrastEnhanced?: RenderTexture;
    sharpened?: RenderTexture;
    CLAHE?: RenderTexture;
    standardizedMuSigma?: RenderTexture;
    standardizedHistogram?: RenderTexture;

    private _pixels: Uint8Array | undefined;

    private constructor(
        instance: Instance,
        webgl: WebGL,
        image_id: string,

        public readonly texture: WebGLTexture,
        dimensions: Dimensions,
        meta: ImageMetadata
    ) {
        super(instance, webgl, image_id, dimensions, meta, texture);
        // this.isGrayscale = isImageGrayscale(canvas);
        this.preprocess();
    }

    private async preprocess() {

        const { cfImageProcessing } = this.webgl;
        const { contrastEnhanced, sharpened, clahe } = await cfImageProcessing.preprocessAll(this);
        this.contrastEnhanced = contrastEnhanced;
        this.sharpened = sharpened;
        this.CLAHE = clahe;

        // if (!this.isGrayscale) {
        //     const { muSigma, hist } = colorStandardization(this);
        //     this.standardizedMuSigma = muSigma;
        //     this.standardizedHistogram = hist;
        //     // this.CLAHE = clahe;
        // } else {
        // Perhaps need a better solution here. 
        // this.standardizedMuSigma = this.contrastEnhanced;
        // this.standardizedHistogram = this.contrastEnhanced;
        // this.CLAHE = this.contrastEnhanced;
        // }
    }

    static fromBitmap(instance: Instance, webgl: WebGL, image_id: string, bitmap: ImageBitmap, dimensions: Dimensions, meta: any) {
        const texture = initTexture(webgl.gl, bitmap);
        return new Image2D(instance, webgl, image_id, texture, dimensions, meta);
    }

    static fromPixelData(instance: Instance, webgl: WebGL, image_id: string, pixelData: Uint8Array, dimensions: Dimensions, meta: any) {
        //TODO: this can be simplified by uploading the pixel data directly to the texture
        const canvas = getCanvas(pixelData, dimensions.width, dimensions.height)
        const texture = initTexture(webgl.gl, canvas);
        return new Image2D(instance, webgl, image_id, texture, dimensions, meta);
    }

    get pixels() {
        if (this._pixels) {
            return this._pixels;
        } else {
            this._pixels = this.getPixelData();
            return this._pixels;
        }
    }

    // private getPixelData(): Uint8Array {
    //     const gl = this.webgl.gl;
    //     const fb = gl.createFramebuffer();
    //     gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    //     gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.texture, 0);
    //     const data = new Uint8Array(4 * this.canvas.width * this.canvas.height);
    //     gl.readPixels(0, 0, this.canvas.width, this.canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, data);
    //     gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    //     gl.deleteFramebuffer(fb);
    //     return data;
    // }

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

function initTexture(gl: WebGL2RenderingContext, canvas: HTMLCanvasElement | ImageBitmap): WebGLTexture {

    const texture = gl.createTexture()!;

    gl.bindTexture(gl.TEXTURE_2D, texture);

    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

    gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA,
        canvas.width,
        canvas.height,
        0,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        canvas
    );
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