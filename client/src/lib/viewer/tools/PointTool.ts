import {
    cycleEnumExtra,
    deletePointAt,
    movePointAt,
    placePoint,
} from "$lib/forms/pointMutations";
import {
    getPointsForImage,
    setPointsForImage,
    type PointSchemaAnalysis,
} from "$lib/forms/pointSchema";
import type { Position2D } from "$lib/types";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay, ToolName, ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

const strokeStyle = "rgba(0, 255, 0, 1)";
const fillStyle = "rgba(255, 255, 255, 0.6)";

export type PointToolOptions = {
    canEdit: boolean;
    analysis: PointSchemaAnalysis;
    label: string;
    getPublicId: () => string;
    getFieldValue: () => unknown;
    setFieldValue: (next: unknown) => void;
    pointStyle?: "rect" | "cross";
    radius?: number;
    /** Optional extra key handler (e.g. ETDRS f/d). */
    onKey?: (e: ViewerEvent<KeyboardEvent>) => void;
};

export class PointTool implements Overlay {
    private activePointIndex: number | undefined;
    private hoverPointIndex: number | undefined;

    toolName: ToolName = "point";
    name: string = "Point";

    private readonly pointStyle: "rect" | "cross";
    private readonly radius: number;

    constructor(private readonly options: PointToolOptions) {
        this.pointStyle = options.pointStyle ?? "cross";
        this.radius = options.radius ?? 16;
        this.name = options.label || "Point";
    }

    private get points() {
        return getPointsForImage(
            this.options.getFieldValue(),
            this.options.getPublicId(),
            this.options.analysis,
        );
    }

    private commit(points: ReturnType<typeof getPointsForImage>) {
        const next = setPointsForImage(
            this.options.getFieldValue(),
            this.options.getPublicId(),
            points,
            this.options.analysis,
        );
        this.options.setFieldValue(next);
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        this.options.onKey?.(e);

        const { event, viewerContext } = e;
        if (
            this.options.analysis.registrationMode &&
            event.key >= "0" &&
            event.key <= "9"
        ) {
            const index = parseInt(event.key, 10) - 1;
            const point = this.points[index];
            if (point) {
                const w = viewerContext.viewerSize.width;
                const w_image = viewerContext.image.width;
                viewerContext.focusPoint(point.x, point.y, (1 * w_image) / w);
            }
        }
    }

    keydown(e: ViewerEvent<KeyboardEvent>) {
        if (!this.options.canEdit) return;
        const { event } = e;
        if (event.key !== "e" && event.key !== "E") return;

        const index = this.activePointIndex ?? this.hoverPointIndex;
        if (index === undefined) return;
        const point = this.points[index];
        if (!point) return;

        const extra = this.options.analysis.enumExtras[0];
        if (!extra) return;

        const updated = cycleEnumExtra(point, extra.key, extra.values);
        const points = [...this.points];
        points[index] = updated;
        this.commit(points);
    }

    pointerdown(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = pointerEvent;
        if (event.shiftKey) return;
        if (!this.options.canEdit) return;

        if (event.button === 0) {
            if (this.hoverPointIndex === undefined) {
                const position = viewerContext.viewerToImageCoordinates(cursor);
                const before = this.points;
                const after = placePoint(
                    before,
                    position,
                    this.options.analysis.cardinality,
                    this.options.analysis.registrationMode,
                );
                // Find which index was written
                let newIndex = after.findIndex(
                    (p, i) => p && (!before[i] || before[i] !== p),
                );
                if (newIndex < 0) newIndex = Math.max(0, after.length - 1);
                this.commit(after);
                this.activePointIndex = newIndex;
                this.hoverPointIndex = newIndex;
            } else {
                this.activePointIndex = this.hoverPointIndex;
            }
        }
    }

    pointerup(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = pointerEvent;
        if (event.shiftKey) return;

        if (!this.options.canEdit) {
            this.activePointIndex = undefined;
            this.hoverPointIndex = this.findHit(cursor, viewerContext);
            return;
        }

        if (event.button === 2) {
            if (this.hoverPointIndex !== undefined) {
                this.commit(
                    deletePointAt(
                        this.points,
                        this.hoverPointIndex,
                        this.options.analysis.registrationMode,
                    ),
                );
            }
        }

        this.activePointIndex = undefined;
        this.hoverPointIndex = this.findHit(cursor, viewerContext);
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        const { cursor, viewerContext } = e;

        if (this.activePointIndex !== undefined && this.options.canEdit) {
            const position = viewerContext.viewerToImageCoordinates(cursor);
            this.commit(
                movePointAt(this.points, this.activePointIndex, position),
            );
        } else {
            this.hoverPointIndex = this.findHit(cursor, viewerContext);
        }
    }

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        const points = this.points;
        const { context2D } = viewerContext;

        context2D.strokeStyle = strokeStyle;
        context2D.fillStyle = strokeStyle;
        context2D.font = "16px sans-serif";

        const r = this.radius;
        const showIndex =
            this.options.analysis.cardinality === "list" ||
            this.options.analysis.registrationMode;

        for (const [index, pt] of points.entries()) {
            if (!pt) continue;
            const p = viewerContext.imageToViewerCoordinates(pt);

            if (this.pointStyle === "rect") {
                context2D.strokeRect(p.x - r, p.y - r, 2 * r, 2 * r);
            } else {
                context2D.beginPath();
                context2D.arc(p.x, p.y, r, 0, 2 * Math.PI);
                context2D.moveTo(p.x - r, p.y);
                context2D.lineTo(p.x + r, p.y);
                context2D.moveTo(p.x, p.y - r);
                context2D.lineTo(p.x, p.y + r);
                context2D.stroke();
            }

            let label = showIndex ? `${index + 1}` : this.options.label;
            for (const extra of this.options.analysis.enumExtras) {
                const v = pt[extra.key];
                if (typeof v === "string") {
                    label = showIndex ? `${index + 1}:${v}` : v;
                    break;
                }
            }
            if (label) {
                context2D.fillText(label, p.x + r, p.y + r + 12);
            }
        }

        context2D.fillStyle = fillStyle;
        const highlightIndex = this.activePointIndex ?? this.hoverPointIndex;
        if (highlightIndex !== undefined) {
            const highlightPoint = points[highlightIndex];
            if (highlightPoint) {
                const p =
                    viewerContext.imageToViewerCoordinates(highlightPoint);
                if (this.pointStyle === "rect") {
                    context2D.fillRect(p.x - r, p.y - r, 2 * r, 2 * r);
                } else {
                    context2D.beginPath();
                    context2D.arc(p.x, p.y, r, 0, 2 * Math.PI);
                    context2D.fill();
                }
            }
        }
        viewerContext.cursorStyle =
            highlightIndex !== undefined ? "pointer" : "default";
    }

    private findHit(
        cursor: Position2D,
        viewerContext: ViewerContext,
    ): number | undefined {
        for (let i = 0; i < this.points.length; i++) {
            const value = this.points[i];
            if (!value) continue;
            const pt = viewerContext.imageToViewerCoordinates(value);
            const dx = pt.x - cursor.x;
            const dy = pt.y - cursor.y;
            if (this.hit(dx, dy)) return i;
        }
    }

    private hit(dx: number, dy: number) {
        if (this.pointStyle === "rect") {
            return Math.abs(dx) < this.radius && Math.abs(dy) < this.radius;
        }
        return dx * dx + dy * dy < this.radius * this.radius;
    }
}
