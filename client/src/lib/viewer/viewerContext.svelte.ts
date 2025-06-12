import type { AbstractImage } from '$lib/webgl/abstractImage';
import type { Shaders } from '$lib/webgl/shaders';
import type { MeasureTool } from './tools/Measure.svelte.js';
import type { EventName, Overlay, PanelName, RenderMode, ViewerEvent, ViewerEventListener, WindowLevel } from './viewer-utils';
import { Matrix } from '$lib/matrix';
import type { Registration } from '$lib/registration/registration.js';
import type { Position2D } from '$lib/types';
import { BaseImageRenderer } from '$lib/webgl/imageRenderer';
import { ScrollOCT } from './controls/scrollOCT';
import { UpdatePosition } from './controls/updatePosition';
import { ZoomPan } from './controls/zoomPan';
import { CursorOverlay } from './overlays/CursorOverlay';
import { HotKeys } from './controls/hotkeys';
import { SvelteSet } from 'svelte/reactivity';

export type cursorStyle = 'default' | 'none' | 'help' | 'pointer' | 'progress' | 'wait' | 'crosshair' | 'text' | 'vertical-text' | 'alias' | 'copy' | 'move' | 'no-drop' | 'not-allowed' | 'grab' | 'grabbing' | 'all-scroll' | 'col-resize' | 'row-resize' | 'n-resize' | 'e-resize' | 's-resize' | 'w-resize' | 'ne-resize' | 'nw-resize' | 'se-resize' | 'sw-resize' | 'ew-resize' | 'ns-resize' | 'nesw-resize' | 'nwse-resize' | 'zoom-in' | 'zoom-out';

export class ViewerContext {

    // perhaps the typing should be improved here
    // using the same interface for repaint (Overlay) and controls (ViewerEventListener)
    private overlays = new Map<symbol, ViewerEventListener | Overlay>();

    hideOverlays: boolean = $state(false);
    renderMode: RenderMode = $state('Original');
    lockScroll: boolean = $state(false);
    windowLevel: WindowLevel = $state({ min: 0, max: 255 });
    cursorStyle: cursorStyle = $state('default');
    active: boolean = $state(false);
    updatePosition: boolean = $state(true);
    viewerPlane: 'PRIMARY' | 'SECONDARY' | 'TERTIARY' = $state('PRIMARY');

    index = $state(0);

    viewerSize: { width: number, height: number } = $state({ width: 100, height: 100 });
    viewingRect: DOMRect = $state(new DOMRect(0, 0, 0, 0));

    imageTransform: Matrix = $state(Matrix.identity);
    transform: Matrix = $state(Matrix.identity);

    stretch: number = $state(1);
    stretchMatrix = $derived(new Matrix(1, 0, 0, 0, this.stretch));

    // image coordinates (pixels) => viewer coordinates (viewer pixels)
    // takes both local image transform and viewer transform into account
    imageViewerTransform: Matrix = $derived(this.transform.multiply(this.imageTransform.multiply(this.stretchMatrix)));
    // viewer space to webgl clip space [-1, 1] x [-1, 1]
    scaleViewerMatrix = $derived(new Matrix(2 / this.viewerSize.width, 0, -1, 0, -2 / this.viewerSize.height, 1));
    // image coordinates to clip space
    webglTransform = $derived(this.scaleViewerMatrix.multiply(this.imageViewerTransform));

    measureTool: MeasureTool | undefined;

    activePanels = new SvelteSet<PanelName>();

    shaders: Shaders;

    canvas2D: HTMLCanvasElement;
    context2D: CanvasRenderingContext2D;

    imageRenderer: BaseImageRenderer;

    constructor(
        public readonly image: AbstractImage,
        public readonly registration: Registration
    ) {

        this.shaders = image.webgl.shaders;
        this.imageRenderer = new BaseImageRenderer(image);

        this.canvas2D = document.createElement('canvas');
        this.context2D = this.canvas2D.getContext('2d')!;

        this.windowLevel = { min: 0, max: 255 };
        if (image.is3D) {
            this.index = Math.round(image.depth / 2);
            if (image.instance.device.model == '3D OCT-1000' ||
                image.instance.device.model == '3D OCT-1000 MARK II' ||
                image.instance.device.model == '3D OCT-2000 FA Plus'
            ) {
                this.windowLevel = { min: 30, max: 225 };
            }
            // aspect ratio for OCT
            if (image.resolution.z) {
                this.stretch = 8 * image.resolution.y / image.resolution.x;
            }
        }
        this.transform = this.getInitTransform();
        this.imageTransform = image.transform;

        if (image.is3D) {
            this.addOverlay(new ScrollOCT());
        }
        this.addOverlay(new UpdatePosition());
        this.addOverlay(new ZoomPan());
        this.addOverlay(new CursorOverlay());
        this.addOverlay(new HotKeys());
    }

    setIndex(i: number) {
        const p = this.registration.getPosition(this.image.image_id);
        let x = 0
        let y = 0;
        if (p) {
            x = p.x;
            y = p.y;
        }
        this.registration.setPosition(this.image.image_id, { x, y, index: i });
        this.index = i;
    }

    initTransform() {
        this.transform = this.getInitTransform();
    }

    /**
     * Takes into account image local transform and ROI to fit the image into the viewer
	
     * @returns transform that fits the image into the viewer
     */
    getInitTransform() {

        let x_min = 0;
        let x_max = this.image.width;
        let y_min = 0;
        let y_max = this.image.height;
        const instance = this.image.instance
        if (instance.cfROI) {
            let center;
            let cx = this.image.width / 2;
            let cy = this.image.height / 2;
            let min_x = 0;
            let max_x = this.image.width;
            let min_y = 0;
            let max_y = this.image.height;
            let radius = Math.min(this.image.width, this.image.height) / 2;
            try {
                ({ center, radius, min_x, max_x, min_y, max_y } = instance.cfROI);
                ([cx, cy] = center);
            } catch (e) {
                console.warn('Error in cfROI', e);

            }
            x_min = Math.max(x_min, cx - radius, min_x);
            x_max = Math.min(x_max, cx + radius, max_x);
            y_min = Math.max(y_min, cy - radius, min_y);
            y_max = Math.min(y_max, cy + radius, max_y);
        }

        const { x: x0, y: y0 } = this.image.transform.apply({ x: x_min, y: y_min });
        const { x: x1, y: y1 } = this.image.transform.apply({ x: x_max, y: y_max });
        x_max = Math.max(x0, x1);
        x_min = Math.min(x0, x1);
        y_max = Math.max(y0, y1);
        y_min = Math.min(y0, y1);

        const w = this.viewerSize.width;
        const h = this.viewerSize.height;

        const roiWidth = x_max - x_min;
        const roiHeight = y_max - y_min;

        const scale = Math.min(w / roiWidth, h / (this.stretch * roiHeight));

        const tx = (w - scale * roiWidth) / 2 - x_min * scale;
        const ty = (h - this.stretch * scale * roiHeight) / 2 - y_min * scale;

        return Matrix.from_translate_scale(tx, ty, scale, scale);

    }

    /**
     * pan the image by the difference between old and new position in viewer coordinates
     */
    pan(oldPosition: Position2D, newPosition: Position2D) {
        this.transform = this.transform.pan(oldPosition, newPosition);
    }
    /**
     * zoom around point in viewer coordinates
     */
    zoom(x: number, y: number, factor: number) {
        this.transform = this.transform.zoom(x, y, factor);
    }
    /**
     * zoom around point in image coordinates	 * 
     */
    focusPoint(x: number, y: number, scale: number) {

        const w = this.viewerSize.width;
        const h = this.viewerSize.height;
        const w_image = this.image.width;
        const h_image = this.image.height;
        const factor = Math.max(w / w_image, h / h_image) * scale / this.transform.scale;
        const p = this.imageToViewerCoordinates({ x, y });

        let transform = this.transform.pan(p, { x: w / 2, y: h / 2 });
        transform = transform.zoom(w / 2, h / 2, factor);

        this.transform = transform;
    }

    get aspectRatio() {
        return this.imageViewerTransform.aspectRatio;
    }

    imageToViewerCoordinates(pixel: Position2D): Position2D {
        return this.imageViewerTransform.apply(pixel);
    }

    viewerToImageCoordinates(cursor: Position2D): Position2D {
        return this.imageViewerTransform.inverse.apply(cursor);
    }

    forwardEvent(eventName: EventName, event: ViewerEvent<any>) {
        for (const overlay of this.overlays.values()) {
            if (eventName in overlay) {
                overlay[eventName]!.bind(overlay)(event);
            }
        }
    }

    /**
     * Add overlay to viewer. An overlay receives pointer events and can draw on top of the image	 * 
     * @param overlay 
     * @returns function that removes overlay when called
     */
    addOverlay(overlay: ViewerEventListener | Overlay) {
        for (const existing of this.overlays.values()) {
            if (existing === overlay) {
                console.warn('Overlay already added');
            }
        }
        const id = Symbol();
        this.overlays.set(id, overlay);
        return () => this.overlays.delete(id);
    }

    repaint() {
        if (!this.viewingRect) {
            return;
        }
        const renderBounds = this.image.getRenderBounds(this.viewingRect);
        if (!renderBounds) {
            return;
        }
        const p = this.registration.getPosition(this.image.image_id);
        if (p) {
            this.index = p.index;
        }

        const renderTarget = { ...renderBounds, framebuffer: null };

        this.imageRenderer.renderImage(this, renderTarget);

        this.context2D.clearRect(0, 0, this.canvas2D.width, this.canvas2D.height);

        this.cursorStyle = 'default';
        if (!this.hideOverlays) {
            for (const overlay of this.overlays.values()) {
                overlay.repaint?.(this, renderTarget);
            }
        }
        this.canvas2D.style.cursor = this.cursorStyle;

    }

}
