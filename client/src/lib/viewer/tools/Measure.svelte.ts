import type { Position2D } from "$lib/types";
import type { RenderTarget } from "$lib/webgl/types";
import {
    lengthText,
    Line,
    type DistanceLines,
} from "$lib/layers/distanceLines.svelte";
import type { Scale } from "$lib/layers/imageScale";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";
import { cased, casedText } from "../overlays/casing";

const radius = 12;
const colour = "rgba(255, 255, 255, 1)";
const selectedColour = "yellow";

/** Distance: paints an image's lines in this viewport and, while armed, draws, moves and deletes them. */
export class MeasureTool implements Overlay {
    private hover: { line: Line; point: Position2D } | undefined;
    private dragging: Position2D | undefined;

    constructor(
        private readonly store: DistanceLines,
        private readonly scale: () => Scale | null,
        private readonly armed: () => boolean,
    ) {}

    private findHit(cursor: Position2D, viewerContext: ViewerContext) {
        for (const line of this.store.lines) {
            if (line.index !== viewerContext.index) continue;
            for (const point of line) {
                const pt = viewerContext.imageToViewerCoordinates(point);
                if (Math.hypot(pt.x - cursor.x, pt.y - cursor.y) < radius)
                    return { point, line };
            }
        }
    }

    pointerdown(e: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = e;
        // Shift+drag pans; the right button does nothing.
        if (!this.armed() || event.shiftKey || event.button !== 0) return;
        const position = viewerContext.viewerToImageCoordinates(cursor);
        const { drawing } = this.store;
        if (drawing) {
            Object.assign(drawing.end, position);
            this.store.drawing = undefined;
            return;
        }
        // The hover is refreshed on pointermove only, so its line may be gone.
        const hover =
            this.hover && this.store.lines.includes(this.hover.line)
                ? this.hover
                : undefined;
        if (hover) {
            this.dragging = hover.point;
            this.store.current = hover.line;
            return;
        }
        const line = new Line(
            { ...position },
            { ...position },
            viewerContext.index,
        );
        this.store.add(line);
        this.store.drawing = line;
    }

    pointerup(e: ViewerEvent<PointerEvent>) {
        if (e.event.shiftKey) return;
        this.dragging = undefined;
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        if (!this.armed()) return;
        const { cursor, viewerContext } = e;
        const moving = this.store.drawing?.end ?? this.dragging;
        if (moving)
            Object.assign(
                moving,
                viewerContext.viewerToImageCoordinates(cursor),
            );
        else this.hover = this.findHit(cursor, viewerContext);
    }

    keydown(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext, cursor } = e;
        if (
            !this.armed() ||
            (event.key !== "Delete" && event.key !== "Backspace")
        )
            return;
        // Del acts at the pointer, so only in the viewport the pointer is over.
        if (!viewerContext.active) return;
        const hit = this.findHit(cursor, viewerContext);
        if (!hit) return;
        this.store.remove(hit.line);
        this.hover = undefined;
    }

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        viewerContext.context2D.textAlign = "center";
        for (const line of this.store.lines) {
            if (line.index === viewerContext.index)
                this.paintLine(line, viewerContext);
        }
        if (!this.armed()) return;
        if (this.hover)
            viewerContext.claimCursor("pointer", CursorPriority.Hover);
        else viewerContext.claimCursor("crosshair", CursorPriority.Tool);
    }

    private paintLine(line: Line, viewerContext: ViewerContext) {
        const ctx = viewerContext.context2D;
        const { x: x0, y: y0 } = viewerContext.imageToViewerCoordinates(
            line.start,
        );
        const { x: x1, y: y1 } = viewerContext.imageToViewerCoordinates(
            line.end,
        );
        const cx = (x0 + x1) / 2;
        const cy = (y0 + y1) / 2;
        const dx = x1 - x0;
        const dy = y1 - y0;
        const l = Math.sqrt(dx * dx + dy * dy) / radius;
        const nx = -dy / l;
        const ny = dx / l;
        // The current line, and the one a Layers row points at, stand out.
        const selected =
            line === this.store.current || line === this.store.highlighted;
        ctx.strokeStyle = selected ? selectedColour : colour;
        ctx.fillStyle = selected ? selectedColour : colour;
        ctx.lineWidth = selected ? 2 : 1;

        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.moveTo(x0 - nx, y0 - ny);
        ctx.lineTo(x0 + nx, y0 + ny);
        ctx.moveTo(x1 - nx, y1 - ny);
        ctx.lineTo(x1 + nx, y1 + ny);
        cased(ctx, () => ctx.stroke());
        casedText(ctx, lengthText(line, this.scale()), cx + 3 * nx, cy - ny);
    }
}
