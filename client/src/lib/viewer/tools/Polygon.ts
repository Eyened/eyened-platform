import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerEvent } from "../viewer-utils";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";
import {
    casedStroke,
    SegmentationTool,
    type DrawingMode,
} from "./segmentation";

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
        viewerContext.claimCursor("crosshair", CursorPriority.Tool);
        if (!this.currentPoints || this.currentPoints.length == 0) return;

        const ctx = viewerContext.context2D;
        const first = this.segmentationToViewer(this.currentPoints[0]);
        let last = first;
        const lasso = new Path2D();
        lasso.moveTo(first.x, first.y);
        for (const point of this.currentPoints.slice(1)) {
            last = this.segmentationToViewer(point);
            lasso.lineTo(last.x, last.y);
        }
        ctx.fillStyle = this.fillColor;
        ctx.fill(lasso);
        casedStroke(ctx, lasso, this.drawingColor);
        // Dashed: the edge the release will close.
        const closing = new Path2D();
        closing.moveTo(last.x, last.y);
        closing.lineTo(first.x, first.y);
        casedStroke(ctx, closing, this.drawingColor, [5, 5]);
    }
}
