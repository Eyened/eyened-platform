import type { Position2D } from "$lib/types";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerContext } from "../viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { SvelteSet } from "svelte/reactivity";

const radius = 12;
const strokeStyle = 'rgba(255, 255, 255, 1)';
const fillStyle = 'rgba(255, 255, 255, 1)';

export class Line {
    start = $state({ x: 0, y: 0 });
    end = $state({ x: 0, y: 0 });

    constructor(start: Position2D, end: Position2D, public readonly index: number) {
        this.start = start;
        this.end = end;
    }
    *[Symbol.iterator]() {
        yield this.start;
        yield this.end;
    }

}

export class MeasureTool implements Overlay {

    hover: { line: Line, point: Position2D } | undefined = undefined;
    dragging: Position2D | undefined = undefined;
    lines = new SvelteSet<Line>();
    highligtLine: Line | undefined = undefined


    imageResX = $state(0);
    imageResY = $state(0);

    dbResAvailable = false;

    constructor(image: AbstractImage) {
        this.imageResX = image.resolution.x;
        this.imageResY = image.resolution.y;
        this.dbResAvailable = image.resolution.x >= 0;

        if (!this.dbResAvailable) {
            this.imageResX = 0;
            this.imageResY = 0;
        }
    }

    setResolution(resolution: number) {
        this.imageResX = resolution;
        this.imageResY = resolution;
    }

    highlight(Line: Line | undefined) {
        this.highligtLine = Line;
    }

    findHit(cursor: Position2D, viewerContext: ViewerContext) {

        for (const line of this.lines) {
            for (const point of line) {
                if (line.index != viewerContext.index) {
                    continue;
                }
                const pt = viewerContext.imageToViewerCoordinates(point);
                const dx = pt.x - cursor.x;
                const dy = pt.y - cursor.y;

                if (dx * dx + dy * dy < radius * radius) {
                    viewerContext.cursorStyle = 'pointer';
                    return { point, line };
                }
            }
        }
        viewerContext.cursorStyle = 'crosshair';

    }

    pointerdown(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = pointerEvent;
        if (event.shiftKey) {
            return;
        }
        // const cursor = viewerContext.imageToViewerCoordinates(position);
        const position = viewerContext.viewerToImageCoordinates(cursor);

        if (this.hover) {
            if (event.button == 2) {
                this.lines.delete(this.hover.line);
                this.hover = this.findHit(cursor, viewerContext);
            } else {
                this.dragging = this.hover.point;
            }

        } else {
            const index = viewerContext.index;
            const line = new Line({ ...position }, { ...position }, index);
            this.lines.add(line);
            this.dragging = line.end;
        }
    }

    pointerup(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event } = pointerEvent;
        if (event.shiftKey) {
            return;
        }
        this.dragging = undefined;
    }

    pointermove(pointerEvent: ViewerEvent<PointerEvent>) {
        const { cursor, viewerContext } = pointerEvent;
        const position = viewerContext.viewerToImageCoordinates(cursor);

        if (this.dragging) {
            Object.assign(this.dragging, position);
        } else {
            this.hover = this.findHit(cursor, viewerContext);
        }
    }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const ctx = viewerContext.context2D;
        ctx.lineWidth = 1;

        ctx.textAlign = "center";
        for (const line of this.lines) {
            if (line.index == viewerContext.index) {
                this.paintLine(line, viewerContext);
            }
        }
        if (this.hover) {
            viewerContext.cursorStyle = 'pointer';
        } else {
            viewerContext.cursorStyle = 'crosshair';
        }
    }

    paintLine(line: Line, viewerContext: ViewerContext) {
        const ctx = viewerContext.context2D;
        const { x: x0, y: y0 } = viewerContext.imageToViewerCoordinates(line.start);
        const { x: x1, y: y1 } = viewerContext.imageToViewerCoordinates(line.end);
        const cx = (x0 + x1) / 2;
        const cy = (y0 + y1) / 2;

        const dx = x1 - x0;
        const dy = y1 - y0;
        const l = Math.sqrt(dx * dx + dy * dy) / radius;
        const nx = -dy / l;
        const ny = dx / l;
        if (this.highligtLine == line) {
            ctx.strokeStyle = 'yellow';
            ctx.fillStyle = 'yellow';
            ctx.lineWidth = 2;
        } else {
            ctx.strokeStyle = strokeStyle;
            ctx.fillStyle = fillStyle;
            ctx.lineWidth = 1;
        }

        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.moveTo(x0 - nx, y0 - ny);
        ctx.lineTo(x0 + nx, y0 + ny);
        ctx.moveTo(x1 - nx, y1 - ny);
        ctx.lineTo(x1 + nx, y1 + ny);
        ctx.stroke();
        ctx.fillText(this.getDistance(line), cx + 3 * nx, cy - ny);

    }

    getDistance(line: Line) {
        const { x: x0, y: y0 } = line.start;
        const { x: x1, y: y1 } = line.end;

        const dx = x1 - x0;
        const dy = y1 - y0;

        const dx_um = this.imageResX * dx;
        const dy_um = this.imageResY * dy;

        const l = Math.sqrt(dx_um * dx_um + dy_um * dy_um);
        if (l > 1000) {
            return `${(l / 1000).toFixed(2)} mm`;
        } else {
            return `${l.toFixed(2)} µm`;
        }

    }
}
