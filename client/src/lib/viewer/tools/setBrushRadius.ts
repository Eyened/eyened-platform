import type { Position2D } from "$lib/types";
import { sizeKey } from "$lib/workspace/paint";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";
import { casedStroke, type PaintView } from "./segmentation";

/** Alt+wheel and Alt+drag change the brush size; draws the brush outline in place of the system cursor. */
export class SetBrushRadiusTool implements Overlay {
    wheelFactor = 1.05;

    private positionStart: Position2D | undefined;
    private radiusStart: number | undefined;
    private lastPosition: Position2D = { x: 0, y: 0 };

    constructor(
        private readonly viewerContext: ViewerContext,
        private readonly view: PaintView,
        /** True draws the outline dashed: Eraser, Enhance Decrease. */
        private readonly dashed: () => boolean,
    ) {}

    private get radius(): number {
        return this.view.paint[sizeKey(this.viewerContext.image)];
    }

    private set radius(size: number) {
        this.view.setSize(this.viewerContext.image, size);
    }

    wheel(e: ViewerEvent<WheelEvent>) {
        if (!e.event.altKey) return;
        this.radius =
            e.event.deltaY > 0
                ? this.radius * this.wheelFactor
                : this.radius / this.wheelFactor;
    }

    pointermove(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, position } = pointerEvent;
        this.lastPosition = position;
        if (event.altKey) {
            if (this.positionStart && this.radiusStart) {
                const dx = this.positionStart.x - position.x;
                this.radius = Math.abs(this.radiusStart - dx);
            } else {
                this.positionStart = position;
                this.radiusStart = this.radius;
            }
        } else {
            // Reset the starting position when Alt key is released
            this.positionStart = undefined;
            this.radiusStart = undefined;
        }
    }

    repaint(viewerContext: ViewerContext) {
        const ctx = viewerContext.context2D;
        const radius = this.radius;
        const center = this.lastPosition;
        const c = viewerContext.imageToViewerCoordinates(center);
        const crx = viewerContext.imageToViewerCoordinates({
            x: center.x + radius,
            y: center.y,
        });
        const cry = viewerContext.imageToViewerCoordinates({
            x: center.x,
            y: center.y + radius,
        });
        const radiusX = crx.x - c.x;
        const radiusY = (cry.y - c.y) * this.viewerContext.aspectRatio;

        // The outline at the real size; a 5 px cross keeps a tiny brush findable.
        const outline = new Path2D();
        outline.ellipse(
            c.x,
            c.y,
            Math.abs(radiusX),
            Math.abs(radiusY),
            0,
            0,
            2 * Math.PI,
        );
        casedStroke(ctx, outline, "white", this.dashed() ? [4, 3] : []);
        const cross = new Path2D();
        cross.moveTo(c.x - 2.5, c.y);
        cross.lineTo(c.x + 2.5, c.y);
        cross.moveTo(c.x, c.y - 2.5);
        cross.lineTo(c.x, c.y + 2.5);
        casedStroke(ctx, cross, "white");

        if (this.positionStart && this.radiusStart) {
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
            casedStroke(ctx, path, "green");
        }

        viewerContext.claimCursor("none", CursorPriority.Hide);
    }
}
