import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { SegmentationTool, type DrawingExecutor } from "./segmentation";

export class BrushTool extends SegmentationTool {
    offscreenCtx: CanvasRenderingContext2D;
    offscreenCanvas: HTMLCanvasElement;

    alpha: number = 0.5;

    constructor(
        drawingExecutor: DrawingExecutor,
        viewerContext: ViewerContext,
        segmentationContext: SegmentationContext,
    ) {
        super(drawingExecutor, viewerContext, segmentationContext);
        // Create an offscreen canvas for drawing the ellipses
        this.offscreenCanvas = document.createElement("canvas");
        this.offscreenCtx = this.offscreenCanvas.getContext("2d")!;
    }

    get brushRadius(): number {
        return this.segmentationContext.brushRadius;
    }

    startDraw(viewerContext: ViewerContext) {
        super.startDraw(viewerContext);
        const { width, height } = viewerContext.canvas2D;
        this.offscreenCanvas.width = width;
        this.offscreenCanvas.height = height;
        this.offscreenCtx.clearRect(0, 0, width, height);
        this.offscreenCtx.fillStyle = this.drawingColor;
    }

    pointerdown(e: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, modifiers } = e;

        this.lastPosition = this.eventToSegmentation(e);

        if (modifiers.alt || modifiers.shift) return;

        if (event.button === 0) this.drawingState = "paint";
        else if (event.button === 2) this.drawingState = "erase";

        this.startDraw(viewerContext);
    }

    pointerup(e: ViewerEvent<PointerEvent>) {
        const { viewerContext } = e;

        this.endDraw(viewerContext);
    }

    pointermove(pointerEvent: ViewerEvent<PointerEvent>) {
        const { modifiers } = pointerEvent;

        if (modifiers.alt) {
            return;
        } else {
            this.lastPosition = this.eventToSegmentation(pointerEvent);
        }

        if (this.drawingState && this.currentPoints) {
            const prev = this.currentPoints[this.currentPoints.length - 1];
            const position = this.eventToSegmentation(pointerEvent);

            const dx = position.x - prev.x;
            const dy = position.y - prev.y;
            const length = Math.sqrt(dx * dx + dy * dy);
            const { rx: segRx } = this.imageBrushRadiiToSegmentation(prev);
            const steps = Math.ceil((8 * length) / Math.max(segRx, 1));
            for (let i = 1; i <= steps; i++) {
                const r = i / steps;
                const pt = {
                    x: prev.x + r * dx,
                    y: prev.y + r * dy,
                };
                this.currentPoints.push(pt);

                const { rx, ry } = this.imageBrushRadiiToSegmentation(pt);
                const p0 = this.segmentationToViewer(pt);
                const p1 = this.segmentationToViewer({ x: pt.x + rx, y: pt.y });
                const p2 = this.segmentationToViewer({ x: pt.x, y: pt.y + ry });
                const vrx = p1.x - p0.x;
                const vry = p2.y - p0.y;
                const path = new Path2D();
                path.ellipse(
                    p0.x,
                    p0.y,
                    Math.abs(vrx),
                    Math.abs(vry),
                    0,
                    0,
                    2 * Math.PI,
                );
                this.offscreenCtx.fill(path);
            }
        }
    }

    executeDraw(
        ctx: CanvasRenderingContext2D,
        _viewerContext: ViewerContext,
    ): void {
        ctx.fillStyle = "white";
        for (const pt of this.currentPoints!) {
            const { rx, ry } = this.imageBrushRadiiToSegmentation(pt);
            const path = new Path2D();
            path.ellipse(pt.x, pt.y, rx, ry, 0, 0, 2 * Math.PI);
            ctx.fill(path);
        }
    }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        super.repaint(viewerContext, renderTarget);
        const ctx = viewerContext.context2D;

        if (!this.drawingState || !this.currentPoints) return;

        if (this.currentPoints) {
            ctx.save();
            ctx.globalAlpha = this.alpha;
            ctx.drawImage(this.offscreenCanvas, 0, 0);
            ctx.restore();
        }
    }
}
