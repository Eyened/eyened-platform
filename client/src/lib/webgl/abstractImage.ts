import { Matrix } from "$lib/matrix";
import type { ImageGET, ModelSegmentationGET, SegmentationGET } from "../../types/openapi_types";
import type { Dimensions, RenderBounds } from "./types";
import type { WebGL } from "./webgl";
import { SvelteMap } from "svelte/reactivity";
import { SegmentationItem } from "./segmentationItem.svelte";

export abstract class AbstractImage {

    public readonly width: number;
    public readonly height: number;
    public readonly depth: number;
    abstract texture: WebGLTexture;

    // in micrometers / pixel
    public readonly resolution: { x: number, y: number, z: number };
    transform: Matrix = Matrix.identity;
    
    // Cache segmentation items per segmentation ID
    public readonly segmentationItems = new SvelteMap<number, SegmentationItem>();
    public readonly orientation: 'axial' | 'enface';
    constructor(
        public readonly instance: ImageGET,
        public readonly webgl: WebGL,
        public readonly image_id: string,
        public readonly dimensions: Dimensions,
        public readonly meta: any) {
        const { width, height, depth, width_mm, height_mm, depth_mm } = this.dimensions;
        this.width = width;
        this.height = height;
        this.depth = depth;


        if (instance.modality === 'OCT') {
            if (instance.resolution_axial && instance.resolution_axial>0) {
                this.orientation = 'axial';
            } else {
                this.orientation = 'enface';
            }
        } else {
            this.orientation = 'enface';
        }

        this.resolution = {
            x: 1000 * width_mm / width,
            y: 1000 * height_mm / height,
            z: 1000 * depth_mm / depth
        };
        this.initTransform();
    }

    abstract is3D: boolean;
    abstract is2D: boolean;
    

    getAspectRatio() {
        const { width, height, width_mm, height_mm } = this.dimensions;
        if (width_mm <= 0 || height_mm <= 0) {
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

    getOrCreateSegmentationItem(segmentation: SegmentationGET | ModelSegmentationGET): SegmentationItem {
        // Use id as key (unique per segmentation)
        const cached = this.segmentationItems.get(segmentation.id);
        if (cached) {
            return cached;
        }

        // Create new segmentation item
        const segmentationItem = new SegmentationItem(this, segmentation);
        this.segmentationItems.set(segmentation.id, segmentationItem);
        return segmentationItem;
    }

    /**
     * Dispose of all resources associated with this image.
     * Should be called when the image is no longer needed, especially before
     * navigating away or destroying the WebGL context.
     */
    dispose(): void {
        // Dispose all segmentation items
        for (const segmentationItem of this.segmentationItems.values()) {
            segmentationItem.dispose();
        }
        this.segmentationItems.clear();
        
        // Clear canvas contexts
        this._drawingContext = null;
        this._ioContext = null;
    }

}