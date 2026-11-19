import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { SegmentationTool, type DrawingMode } from "./segmentation";

const lineWidth = 2;

/** Drag round an area to fill it, or with X, to erase it. */
export class PolygonTool extends SegmentationTool {
    protected nextMode(): DrawingMode {
        return this.view.remove ? "erase" : "paint";
    }

    pointerdown(e: ViewerEvent<PointerEvent>) {
        const { event } = e;
        this.lastPosition = this.eventToSegmentation(e);
        if (event.button !== 0 || event.altKey || event.shiftKey) return;
        if (this.stroke) return;
        this.startDraw(e.viewerContext);
    }

    pointerup(e: ViewerEvent<PointerEvent>) {
        this.endDraw(e.viewerContext);
    }

    pointermove(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event } = pointerEvent;
        if (event.altKey || event.shiftKey) return;
        this.lastPosition = this.eventToSegmentation(pointerEvent);
        if (this.currentPoints) this.currentPoints.push(this.lastPosition);
    }

    executeDraw(
        ctx: CanvasRenderingContext2D,
        _viewerContext: ViewerContext,
    ): void {
        ctx.fillStyle = "white";
        ctx.beginPath();
        const p = this.currentPoints![0];
        ctx.moveTo(p.x, p.y);
        for (let i = 1; i < this.currentPoints!.length; i++) {
            ctx.lineTo(this.currentPoints![i].x, this.currentPoints![i].y);
        }
        ctx.lineTo(p.x, p.y);
        ctx.fill();
    }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        super.repaint(viewerContext, renderTarget);
        if (!this.currentPoints || this.currentPoints.length == 0) return;

        const ctx = viewerContext.context2D;
        ctx.lineWidth = lineWidth;
        ctx.strokeStyle = this.drawingColor;
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
