import type { Position2D } from "$lib/types";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { ViewerContext } from "../viewerContext.svelte";

export class SetBrushRadiusTool implements Overlay {
    wheelFactor = 1.05;
    lineWidth = 1;

    private positionStart: Position2D | undefined;
    private radiusStart: number | undefined;
    private lastPosition: Position2D = { x: 0, y: 0 };

    constructor(
        private readonly viewerContext: ViewerContext,
        private readonly segmentationContext: SegmentationContext) {
    }

    wheel(e: ViewerEvent<WheelEvent>) {
        if (e.event.altKey) {
            if (e.event.deltaY > 0) {
                this.segmentationContext.brushRadius *= this.wheelFactor;
            } else {
                this.segmentationContext.brushRadius /= this.wheelFactor;
            }
        }
    }

    pointermove(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, position } = pointerEvent;
        this.lastPosition = position;
        if (event.altKey) {
            // update brush radius
            if (this.positionStart && this.radiusStart) {
                const x_start = this.positionStart.x + this.radiusStart;
                const x_current = position.x + this.radiusStart;
                const dx = x_start - x_current;

                this.segmentationContext.brushRadius = Math.abs(this.radiusStart - dx);

            } else {
                this.positionStart = position;
                this.radiusStart = this.segmentationContext.brushRadius;
            }
        } else {
            // Reset the starting position when Alt key is released
            this.positionStart = undefined;
            this.radiusStart = undefined;
        }
    }

    keydown(keyEvent: ViewerEvent<KeyboardEvent>) {
        const { event: { repeat, key } } = keyEvent;
        if (repeat) return;
        if (key >= '1' && key <= '9') {
            this.segmentationContext.brushRadius = Math.log(parseInt(key));
        }

    }

    keyup(keyEvent: ViewerEvent<KeyboardEvent>) {
        const { event: { key } } = keyEvent;

        if (key === '=' || key === '+') {
            this.segmentationContext.brushRadius *= this.wheelFactor;
        }
        if (key === '-') {
            this.segmentationContext.brushRadius /= this.wheelFactor;
        }
    }

    repaint(viewerContext: ViewerContext) {
        const ctx = viewerContext.context2D;
        ctx.lineWidth = this.lineWidth;
        ctx.strokeStyle = 'white';

        const radius = this.segmentationContext.brushRadius;

        const centre = this.lastPosition;
        const c = viewerContext.imageToViewerCoordinates(centre);
        const crx = viewerContext.imageToViewerCoordinates({ x: centre.x + radius, y: centre.y });
        const cry = viewerContext.imageToViewerCoordinates({ x: centre.x, y: centre.y + radius });
        const radiusX = crx.x - c.x;
        const radiusY = (cry.y - c.y) * this.viewerContext.aspectRatio;
        const { x, y } = c;

        const path = new Path2D();
        path.ellipse(x, y, radiusX, radiusY, 0, 0, 2 * Math.PI);
        ctx.stroke(path);

        if (this.positionStart && this.radiusStart) {
            ctx.strokeStyle = 'green';
            const path = new Path2D();
            const d = 5;
            path.moveTo(c.x, c.y);
            path.lineTo(c.x + d, c.y + d);
            path.moveTo(c.x, c.y);
            path.lineTo(c.x + d, c.y - d);
            path.moveTo(c.x, c.y);
            path.lineTo(crx.x, c.y);
            path.lineTo(crx.x - d, c.y + d);
            path.moveTo(crx.x, c.y);
            path.lineTo(crx.x - d, c.y - d);

            ctx.stroke(path);

        }

        viewerContext.cursorStyle = 'none';

    }
}