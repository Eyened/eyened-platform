import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { SegmentationTool, type DrawingExecutor } from "./segmentation";

const lineWidth = 2;

export class PolygonTool extends SegmentationTool {
    constructor(
        drawingExecutor: DrawingExecutor,
        viewerContext: ViewerContext,
        segmentationContext: SegmentationContext,
    ) {
        super(drawingExecutor, viewerContext, segmentationContext);
    }

    pointerdown(e: ViewerEvent<PointerEvent>) {
        const { event } = e;
        this.lastPosition = this.eventToSegmentation(e);

        if (event.altKey || event.shiftKey) return;

        if (event.button === 0) this.drawingState = "paint";
        else if (event.button === 2) this.drawingState = "erase";

        this.startDraw(e.viewerContext);
    }

    pointerup(e: ViewerEvent<PointerEvent>) {
        const { viewerContext } = e;
        this.endDraw(viewerContext);
    }

    pointermove(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event } = pointerEvent;
        if (event.altKey || event.shiftKey) {
            return;
        }
        this.lastPosition = this.eventToSegmentation(pointerEvent);

        if (this.drawingState && this.currentPoints) {
            this.currentPoints.push(this.eventToSegmentation(pointerEvent));
        }
    }

    executeDraw(
        ctx: CanvasRenderingContext2D,
        _viewerContext: ViewerContext,
    ): void {
        ctx.fillStyle = "white";

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
        if (
            !this.drawingState ||
            !this.currentPoints ||
            this.currentPoints.length == 0
        )
            return;

        const ctx = viewerContext.context2D;

        ctx.lineWidth = lineWidth;

        if ((this.drawingState === "paint") !== flipDrawErase) {
            ctx.strokeStyle = this.paintColor;
        } else {
            ctx.strokeStyle = this.eraseColor;
        }
        ctx.fillStyle = this.fillColor;
        ctx.setLineDash([]);

        ctx.beginPath();
        let p = this.segmentationToViewer(this.currentPoints[0]);
        ctx.moveTo(p.x, p.y);
        for (let i = 1; i < this.currentPoints.length; i++) {
            p = this.segmentationToViewer(this.currentPoints[i]);
            ctx.lineTo(p.x, p.y);
        }
        ctx.fill();
        ctx.stroke();

        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        p = this.segmentationToViewer(this.currentPoints[0]);
        ctx.moveTo(p.x, p.y);
        p = this.segmentationToViewer(
            this.currentPoints[this.currentPoints.length - 1],
        );
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
        ctx.setLineDash([]);
    }
}
