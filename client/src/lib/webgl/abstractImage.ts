import type { Dimensions, RenderBounds } from "./types";
import type { WebGL } from "./webgl";
import type { Instance } from "$lib/datamodel/instance";
import { data } from "$lib/datamodel/model";
import type { Annotation } from "$lib/datamodel/annotation";
import type { FilterList } from "$lib/datamodel/itemList";
import { Matrix } from "$lib/matrix";
import { SegmentationController } from "./SegmentationController";

export abstract class AbstractImage {

    public readonly width: number;
    public readonly height: number;
    public readonly depth: number;

    public readonly segmentationController: SegmentationController;

    // in micrometers / pixel
    public readonly resolution: { x: number, y: number, z: number };
    transform: Matrix = Matrix.identity;

    constructor(
        public readonly instance: Instance,
        public readonly webgl: WebGL,
        public readonly image_id: string,
        public readonly dimensions: Dimensions,
        public readonly meta: any,
        public readonly texture: WebGLTexture) {
        const { width, height, depth, width_mm, height_mm, depth_mm } = this.dimensions;
        this.width = width;
        this.height = height;
        this.depth = depth;

        this.segmentationController = new SegmentationController(this);

        this.resolution = { x: 1000 * width_mm / width, y: 1000 * height_mm / height, z: 1000 * depth_mm / depth };
        this.initTransform();
    }

    abstract is3D: boolean;
    abstract is2D: boolean;


    get segmentationAnnotations(): FilterList<Annotation> {
        const filter = (annotation: Annotation) => {
            const { annotationType, feature } = annotation;
            if (annotation.instance !== this.instance) return false;

            if (!annotationType.name.includes('Segmentation')) return false;
            if (feature.name == 'Macular layers') return false;
            if (annotationType.name == 'Segmentation OCT Enface' && this.is3D) return false;
            if (annotationType.name == 'Segmentation OCT B-scan' && !this.is3D) return false;
            return true;
        };
        return data.annotations.filter(filter);
    }

    getAspectRatio() {
        const { width, height, width_mm, height_mm } = this.dimensions;
        if (width_mm == -1) {
            return 1;
        }
        return (height * width_mm) / (height_mm * width);
    }

    initTransform() {
        const aspectRatio = this.getAspectRatio();
        this.transform = Matrix.from_translate_scale(0, 0, aspectRatio, 1);
    }

    getRenderBounds(rect: DOMRect): RenderBounds | null {
        const gl = this.webgl.gl;

        const canvas: HTMLCanvasElement = gl.canvas as HTMLCanvasElement;

        if (
            rect.bottom < 0 ||
            rect.top > canvas.clientHeight ||
            rect.right < 0 ||
            rect.left > canvas.clientWidth
        ) {
            return null; // it's off screen
        }
        const width = rect.width + 1;//rect.right - rect.left + 1;
        const height = rect.height;//rect.bottom - rect.top;
        const left = rect.left;
        const bottom = canvas.clientHeight - rect.bottom;//canvas.clientHeight - rect.bottom + 1;
        const result = { left, bottom, width, height };
        return result;
    }

    // Segmentations with the same internal format reuse the same swapbuffer
    // used to draw via passing shader on the gpu
    _swapBuffers = new Map<number, WebGLTexture>();
    getSwapBuffer(internalFormat: number, initializer: () => WebGLTexture): WebGLTexture {
        if (!this._swapBuffers.has(internalFormat)) {
            this._swapBuffers.set(internalFormat, initializer());
        }
        return this._swapBuffers.get(internalFormat)!
    }

    setSwapBuffer(internalFormat: number, texture: WebGLTexture) {
        this._swapBuffers.set(internalFormat, texture);
    }

    getTextureForCanvas(canvas: HTMLCanvasElement) {
        // upload canvas to texture
        // reuse the same texture 
        const gl = this.webgl.gl;
        gl.bindTexture(gl.TEXTURE_2D, this.textureIO);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, canvas);
        return this.textureIO;
    }


    /**
     * Get a canvas context that can be used to draw annotations or export the segmentation
     * the same canvas is reused, so meant for single use only
     * it is cleared before each use
     */
    _drawingContext: CanvasRenderingContext2D | null = null;
    getDrawingCtx() {
        if (!this._drawingContext) {
            // create empty canvas used from drawing annotations
            const canvas = document.createElement('canvas');
            canvas.width = this.width;
            canvas.height = this.height;
            this._drawingContext = canvas.getContext('2d', { willReadFrequently: true })!;
        }
        this._drawingContext.clearRect(0, 0, this.width, this.height);
        return this._drawingContext;
    }

    /**
     * Get a canvas context that can be used to export segmentations
     * the same canvas is reused, so meant for single use only
     * it is cleared before each use
     */
    _ioContext: CanvasRenderingContext2D | null = null;
    getIOCtx() {
        if (!this._ioContext) {
            // create empty canvas used from drawing annotations
            const canvas = document.createElement('canvas');
            canvas.width = this.width;
            canvas.height = this.height;
            this._ioContext = canvas.getContext('2d', { willReadFrequently: true })!;
        }
        this._ioContext.clearRect(0, 0, this.width, this.height);
        return this._ioContext;
    }

    _textureIO: WebGLTexture | null = null;
    get textureIO() {
        if (!this._textureIO) {
            this._textureIO = this.createTexture();
        }
        return this._textureIO;
    }

    createTexture() {
        const gl = this.webgl.gl;
        const texture = gl.createTexture()!;
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, this.width, this.height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.bindTexture(gl.TEXTURE_2D, null);
        return texture;
    }
    createTextureR8UI() {
        const gl = this.webgl.gl;
        const texture = gl.createTexture()!;
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8UI, this.width, this.height, 0, gl.RED_INTEGER, gl.UNSIGNED_BYTE, null);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.bindTexture(gl.TEXTURE_2D, null);
        return texture;
    }
}