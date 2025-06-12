import type { Position2D } from "$lib/types";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay, ToolName, ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

const strokeStyle = 'rgba(0, 255, 0, 1)';
const fillStyle = 'rgba(255, 255, 255, 0.6)';

export type PointList = (Position2D | undefined)[];

export class RegistrationTool implements Overlay {

    // public readonly points = new WritableStore<PointList | undefined>(undefined);
    private activePointIndex: number | undefined;
    private hoverPointIndex: number | undefined

    toolName: ToolName = 'registration';
    name: string = 'Registration';

    constructor(
        private points: PointList,
        private updateCallback: (points: PointList) => void,
        private pointStyle: 'rect' | 'cross' = 'cross',
        private radius: number = 16
    ) { }

    private update() {
        this.updateCallback(this.points);
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext } = e;
        // if it's a number, zoom around the point
        if (event.key >= '0' && event.key <= '9') {
            const index = parseInt(event.key) - 1;
            const point = this.points?.[index];
            if (point) {
                const w = viewerContext.viewerSize.width;
                const w_image = viewerContext.image.width;
                viewerContext.focusPoint(point.x, point.y, 1 * w_image / w);
            }
        }
    }


    pointerdown(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = pointerEvent;
        if (event.shiftKey) return;


        if (event.button === 0) {
            if (this.hoverPointIndex === undefined) {
                const position = viewerContext.viewerToImageCoordinates(cursor);
                this.addPoint(position);
                this.hoverPointIndex = this.activePointIndex;
            } else {
                this.activePointIndex = this.hoverPointIndex;
            }
        }
    }

    pointerup(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = pointerEvent;
        if (event.shiftKey) return;
        if (event.button === 0) {
            if (this.activePointIndex !== undefined) {
                this.update();
            }
        }
        if (event.button === 2) {
            if (this.hoverPointIndex !== undefined) {
                this.removePoint();
                this.update();
            }
        }
        this.activePointIndex = undefined;
        this.hoverPointIndex = this.findHit(cursor, viewerContext)

    }

    private addPoint(position: Position2D) {
        if (!this.points)
            return
        for (let i = 0; i <= this.points.length; i++) {
            if (!this.points[i]) {
                this.activePointIndex = i;
                break
            }
        }
        if (this.activePointIndex === undefined) {
            this.activePointIndex = this.points.length;
        }
        this.points[this.activePointIndex] = position;
    }

    private removePoint() {
        if (!this.points)
            return;
        const index = this.hoverPointIndex!;
        if (index == this.points.length - 1) {
            this.points.splice(index, 1);
        } else {
            this.points[index] = undefined;
        }
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        if (!this.points)
            return;
        const { cursor, viewerContext } = e;

        if (this.activePointIndex !== undefined) {
            const point = this.points[this.activePointIndex]!;
            const position = viewerContext.viewerToImageCoordinates(cursor);
            Object.assign(point, position);
        } else {
            this.hoverPointIndex = this.findHit(cursor, viewerContext);
        }
    }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        if (!this.points)
            return;

        const { context2D } = viewerContext;

        context2D.strokeStyle = strokeStyle;
        context2D.fillStyle = strokeStyle;
        context2D.font = '16px sans-serif';

        const r = this.radius;

        for (const [index, pt] of this.points.entries()) {
            if (!pt) continue;
            const p = viewerContext.imageToViewerCoordinates(pt);

            if (this.pointStyle == 'rect') {
                context2D.strokeRect(p.x - r, p.y - r, 2 * r, 2 * r);
            } else {
                context2D.beginPath();
                context2D.arc(p.x, p.y, r, 0, 2 * Math.PI);
                context2D.moveTo(p.x - r, p.y)
                context2D.lineTo(p.x + r, p.y)
                context2D.moveTo(p.x, p.y - r)
                context2D.lineTo(p.x, p.y + r)

                context2D.stroke();
            }
            context2D.fillText(`${index + 1}`, p.x + r, p.y + r + 12);
        }
        context2D.fillStyle = fillStyle;

        const highlightIndex = this.activePointIndex ?? this.hoverPointIndex;
        if (highlightIndex !== undefined) {
            const highlightPoint = this.points[highlightIndex]!;
            const p = viewerContext.imageToViewerCoordinates(highlightPoint);

            if (this.pointStyle == 'rect') {
                context2D.fillRect(p.x - r, p.y - r, 2 * r, 2 * r);
            } else {
                context2D.beginPath();
                context2D.arc(p.x, p.y, r, 0, 2 * Math.PI);
                context2D.fill();
            }

        }
        viewerContext.cursorStyle = highlightIndex ? 'pointer' : 'default';

    }


    private findHit(cursor: Position2D, viewerContext: ViewerContext): number | undefined {
        if (!this.points)
            return;

        for (let i = 0; i < this.points.length; i++) {
            const value = this.points[i]
            if (!value) {
                continue;
            }
            const pt = viewerContext.imageToViewerCoordinates(value);

            const dx = pt.x - cursor.x;
            const dy = pt.y - cursor.y;

            if (this.hit(dx, dy)) {
                return i;
            }
        }
    }

    private hit(dx: number, dy: number) {
        if (this.pointStyle == 'rect') {
            return Math.abs(dx) < this.radius && Math.abs(dy) < this.radius;
        }
        else {
            return (dx * dx + dy * dy) < (this.radius * this.radius);
        }
    }
}