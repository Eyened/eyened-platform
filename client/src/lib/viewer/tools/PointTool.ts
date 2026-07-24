import type { PointMarkerStyle } from "$lib/config/clientDefaults";
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

const defaultStroke = "rgba(0, 255, 0, 1)";
const fillStyle = "rgba(255, 255, 255, 0.6)";

/** Live PointTool instances — used so empty-click placement ignores siblings' hits. */
const liveTools = new Set<PointTool>();

export type PointToolOptions = {
    canEdit: boolean;
    analysis: PointSchemaAnalysis;
    label: string;
    getPublicId: () => string;
    getFieldValue: () => unknown;
    setFieldValue: (next: unknown) => void;
    pointStyle?: PointMarkerStyle;
    radius?: number;
    color?: string;
    /**
     * When false, this tool still paints and handles hit/drag/delete, but does
     * not place on empty clicks. Defaults to true.
     */
    isPlacementTarget?: () => boolean;
    /** Called when the user starts interacting with one of this tool's points. */
    onBecomePlacementTarget?: () => void;
    /**
     * Keyboard shortcut: keydown places/starts drag at cursor; keyup releases
     * (same as pointerup). Case-insensitive single character (e.g. "f").
     */
    placeKey?: string;
};

export class PointTool implements Overlay {
    private activePointIndex: number | undefined;
    private hoverPointIndex: number | undefined;

    toolName: ToolName = "point";
    name: string = "Point";

    private readonly pointStyle: PointMarkerStyle;
    private readonly radius: number;
    private readonly color: string;

    constructor(private readonly options: PointToolOptions) {
        this.pointStyle = options.pointStyle ?? "circle";
        this.radius = options.radius ?? 16;
        this.color = options.color ?? defaultStroke;
        this.name = options.label || "Point";
        liveTools.add(this);
    }

    /** Remove from the live registry (call when detaching the overlay). */
    destroy() {
        liveTools.delete(this);
    }

    private get points() {
        return getPointsForImage(
            this.options.getFieldValue(),
            this.options.getPublicId(),
            this.options.analysis,
        );
    }

    private isPlacementTarget() {
        return this.options.isPlacementTarget?.() ?? true;
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

    /** True if this tool owns a marker under the cursor. */
    hits(cursor: Position2D, viewerContext: ViewerContext): boolean {
        return this.findHit(cursor, viewerContext) !== undefined;
    }

    /**
     * Place/replace at image coords under the viewer cursor (e.g. keyboard shortcut).
     * Does not consult isPlacementTarget — caller decides when this is appropriate.
     */
    placeAtCursor(viewerContext: ViewerContext, cursor: Position2D) {
        if (!this.options.canEdit) return;
        const position = viewerContext.viewerToImageCoordinates(cursor);
        const before = this.points;
        const after = placePoint(
            before,
            position,
            this.options.analysis.cardinality,
            this.options.analysis.registrationMode,
        );
        let newIndex = after.findIndex(
            (p, i) => p && (!before[i] || before[i] !== p),
        );
        if (newIndex < 0) newIndex = Math.max(0, after.length - 1);
        this.commit(after);
        this.activePointIndex = newIndex;
        this.hoverPointIndex = newIndex;
        this.options.onBecomePlacementTarget?.();
    }

    private siblingOwnsHit(
        cursor: Position2D,
        viewerContext: ViewerContext,
    ): boolean {
        for (const tool of liveTools) {
            if (tool !== this && tool.hits(cursor, viewerContext)) return true;
        }
        return false;
    }

    private siblingHasHighlight(): boolean {
        for (const tool of liveTools) {
            if (tool === this) continue;
            if (
                tool.activePointIndex !== undefined ||
                tool.hoverPointIndex !== undefined
            ) {
                return true;
            }
        }
        return false;
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext, cursor } = e;

        if (
            this.options.placeKey &&
            event.key.toLowerCase() === this.options.placeKey.toLowerCase()
        ) {
            this.activePointIndex = undefined;
            this.hoverPointIndex = this.findHit(cursor, viewerContext);
        }

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
        const { event, viewerContext, cursor } = e;

        if (
            this.options.placeKey &&
            !event.repeat &&
            event.key.toLowerCase() === this.options.placeKey.toLowerCase()
        ) {
            this.placeAtCursor(viewerContext, cursor);
            return;
        }

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
            const hit = this.findHit(cursor, viewerContext);
            if (hit !== undefined) {
                this.activePointIndex = hit;
                this.hoverPointIndex = hit;
                this.options.onBecomePlacementTarget?.();
                return;
            }

            // Empty click: only the placement target places, and only if no
            // sibling tool owns a marker here.
            if (!this.isPlacementTarget()) return;
            if (this.siblingOwnsHit(cursor, viewerContext)) return;

            this.placeAtCursor(viewerContext, cursor);
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
            const hit = this.findHit(cursor, viewerContext);
            if (hit !== undefined) {
                this.options.onBecomePlacementTarget?.();
                this.commit(
                    deletePointAt(
                        this.points,
                        hit,
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
        const highlightIndex = this.activePointIndex ?? this.hoverPointIndex;

        const { context2D } = viewerContext;
        const strokeStyle = this.color;

        context2D.strokeStyle = strokeStyle;
        context2D.fillStyle = strokeStyle;
        context2D.font = "16px sans-serif";
        context2D.lineWidth = this.isPlacementTarget() ? 1.25 : 0.75;

        const r = this.radius;
        const showIndex =
            this.options.analysis.cardinality === "list" ||
            this.options.analysis.registrationMode;

        for (const [index, pt] of points.entries()) {
            if (!pt) continue;
            const p = viewerContext.imageToViewerCoordinates(pt);
            this.strokeMarker(context2D, p, r);

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
        if (highlightIndex !== undefined) {
            const highlightPoint = points[highlightIndex];
            if (highlightPoint) {
                const p =
                    viewerContext.imageToViewerCoordinates(highlightPoint);
                this.fillMarker(context2D, p, r);
            }
            viewerContext.cursorStyle = "pointer";
        } else if (
            this.options.canEdit &&
            this.isPlacementTarget() &&
            !this.siblingHasHighlight()
        ) {
            viewerContext.cursorStyle = "crosshair";
        }
    }

    private strokeMarker(
        ctx: CanvasRenderingContext2D,
        p: Position2D,
        r: number,
    ) {
        if (this.pointStyle === "rect") {
            ctx.strokeRect(p.x - r, p.y - r, 2 * r, 2 * r);
            return;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
        if (this.pointStyle === "cross") {
            ctx.moveTo(p.x - r, p.y);
            ctx.lineTo(p.x + r, p.y);
            ctx.moveTo(p.x, p.y - r);
            ctx.lineTo(p.x, p.y + r);
        }
        ctx.stroke();
    }

    private fillMarker(
        ctx: CanvasRenderingContext2D,
        p: Position2D,
        r: number,
    ) {
        if (this.pointStyle === "rect") {
            ctx.fillRect(p.x - r, p.y - r, 2 * r, 2 * r);
            return;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
        ctx.fill();
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
