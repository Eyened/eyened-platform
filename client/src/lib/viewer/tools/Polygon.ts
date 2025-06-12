import { SegmentationTool, type DrawingExecutor } from "./segmentation";
import type { ViewerEvent } from "../viewer-utils";
import type { RenderTarget } from "$lib/webgl/types";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { ViewerContext } from "../viewerContext.svelte";

const lineWidth = 2;


export class PolygonTool extends SegmentationTool {

	constructor(
		drawingExecutor: DrawingExecutor,
		viewerContext: ViewerContext,
		segmentationContext: SegmentationContext) {
		super(drawingExecutor, viewerContext, segmentationContext);
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
		const { event, position } = pointerEvent;
		if (event.altKey || event.shiftKey) {
			return;
		}
		this.lastPosition = position;

		if (this.drawingState && this.currentPoints) {
			this.currentPoints.push(position);
		}
	}

	executeDraw(ctx: CanvasRenderingContext2D, viewerContext: ViewerContext): void {
		ctx.fillStyle = 'white';

		ctx.beginPath();
		let p = this.currentPoints![0];
		ctx.moveTo(p.x, p.y);
		for (let i = 1; i < this.currentPoints!.length; i++) {
			ctx.lineTo(this.currentPoints![i].x, this.currentPoints![i].y);
		}
		ctx.lineTo(p.x, p.y);
		ctx.fill();
	}

	repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        super.repaint(viewerContext, renderTarget);
		const flipDrawErase = this.flipDrawErase;
		if (!this.drawingState || !this.currentPoints || this.currentPoints.length == 0) return;

		const ctx = viewerContext.context2D;

		ctx.lineWidth = lineWidth;

		if ((this.drawingState === 'paint') !== flipDrawErase) {
			ctx.strokeStyle = this.paintColor;
		} else {
			ctx.strokeStyle = this.eraseColor;
		}
		// ctx.strokeStyle = getDrawingColor(this.drawingState, flipDrawErase, paintColor, eraseColor);
		ctx.fillStyle = this.fillColor;
		ctx.setLineDash([]);

		// stroke around the current area
		ctx.beginPath();
		let p = viewerContext.imageToViewerCoordinates(this.currentPoints[0]);
		ctx.moveTo(p.x, p.y);
		for (let i = 1; i < this.currentPoints.length; i++) {
			p = viewerContext.imageToViewerCoordinates(this.currentPoints[i]);
			ctx.lineTo(p.x, p.y);
		}
		ctx.fill();
		ctx.stroke();

		// close loop with dashed line
		ctx.setLineDash([5, 5]);
		ctx.beginPath();
		p = viewerContext.imageToViewerCoordinates(this.currentPoints[0]);
		ctx.moveTo(p.x, p.y);
		p = viewerContext.imageToViewerCoordinates(this.currentPoints[this.currentPoints.length - 1]);
		ctx.lineTo(p.x, p.y);
		ctx.stroke();
		ctx.setLineDash([]);
	}

}