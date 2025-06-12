import type { SegmentationContext } from '$lib/viewer-window/panelSegmentation/segmentationContext.svelte';
import type { RenderTarget } from '$lib/webgl/types';
import type { ViewerEvent } from '../viewer-utils';
import type { ViewerContext } from '../viewerContext.svelte';
import { SegmentationTool, type DrawingExecutor } from './segmentation';


export class BrushTool extends SegmentationTool {

	offscreenCtx: CanvasRenderingContext2D;
	offscreenCanvas: HTMLCanvasElement;

	alpha: number = 0.5;
	viewerWidth: number;
	viewerHeight: number;

	constructor(
		drawingExecutor: DrawingExecutor,
		viewerContext: ViewerContext,
		segmentationContext: SegmentationContext
	) {
		super(drawingExecutor, viewerContext, segmentationContext);
		const { width, height } = viewerContext.canvas2D; // viewer size
		this.viewerWidth = width;
		this.viewerHeight = height;
		// Create an offscreen canvas for drawing the ellipses
		this.offscreenCanvas = document.createElement('canvas');
		this.offscreenCanvas.width = width;
		this.offscreenCanvas.height = height;
		this.offscreenCtx = this.offscreenCanvas.getContext('2d')!;
	}

	get brushRadius(): number {
		return this.segmentationContext.brushRadius;
	}
	
	startDraw() {
		super.startDraw();
		this.offscreenCtx.clearRect(0, 0, this.viewerWidth, this.viewerHeight);
		this.offscreenCtx.fillStyle = this.drawingColor;
	}


	pointerdown(e: ViewerEvent<PointerEvent>) {
		const { event, position } = e;

		this.lastPosition = position;

		if (event.altKey || event.shiftKey) return;

		if (event.button === 0) this.drawingState = 'paint';
		else if (event.button === 2) this.drawingState = 'erase';

		this.startDraw();
	}

	pointerup(e: ViewerEvent<PointerEvent>) {
		const { viewerContext } = e;

		this.endDraw(viewerContext);
	}


	pointermove(pointerEvent: ViewerEvent<PointerEvent>) {
		const { event, position, viewerContext } = pointerEvent;

		if (event.altKey) {
			return;
		} else {
			this.lastPosition = position;
		}

		if (this.drawingState && this.currentPoints) {

			// deduce brush radius in viewer coordinates
			const p0 = this.viewerContext.imageToViewerCoordinates({ x: 0, y: 0 });
			const p1 = this.viewerContext.imageToViewerCoordinates({ x: this.brushRadius, y: this.brushRadius * viewerContext.aspectRatio });
			const rx = p1.x - p0.x;
			const ry = p1.y - p0.y;

			const prev = this.currentPoints[this.currentPoints.length - 1];

			const dx = position.x - prev.x;
			const dy = position.y - prev.y;
			const length = Math.sqrt(dx * dx + dy * dy);
			const steps = Math.ceil(8 * length / this.brushRadius);
			for (let i = 1; i <= steps; i++) {
				const r = i / steps;
				const pt = {
					x: prev.x + r * dx,
					y: prev.y + r * dy
				};
				this.currentPoints.push(pt);

				const p = viewerContext.imageToViewerCoordinates(pt);
				const path = new Path2D();
				path.ellipse(p.x, p.y, rx, ry, 0, 0, 2 * Math.PI);
				this.offscreenCtx.fill(path);
			}
		}
	}


	executeDraw(ctx: CanvasRenderingContext2D, viewerContext: ViewerContext): void {

		ctx.fillStyle = 'white';
		const radiusX = this.brushRadius;
		const radiusY = this.brushRadius * viewerContext.aspectRatio;
		for (const pt of this.currentPoints!) {
			const path = new Path2D();
			path.ellipse(pt.x, pt.y, radiusX, radiusY, 0, 0, 2 * Math.PI);
			ctx.fill(path);
		}

	}

	repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        super.repaint(viewerContext, renderTarget);
		const ctx = viewerContext.context2D;
		if (!this.drawingState || !this.currentPoints) return;

		if (this.currentPoints) {
			ctx.globalAlpha = this.alpha;
			ctx.drawImage(this.offscreenCanvas, 0, 0);
			ctx.globalAlpha = 1.0;
		}
	}

}