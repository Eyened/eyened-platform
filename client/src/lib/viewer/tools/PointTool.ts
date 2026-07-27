import type { PointMarkerStyle } from "$lib/config/clientDefaults";
import type { PointAdapter } from "$lib/forms/pointAdapters";
import {
    cycleEnumExtra,
    deletePointAt,
    movePointAt,
    placePoint,
    placePointAt,
} from "$lib/forms/pointMutations";
import type { ImagePoint, PointList } from "$lib/forms/pointSchema";
import type { Position2D } from "$lib/types";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay, ToolName, ViewerEvent } from "../viewer-utils";
import {
    CursorPriority,
    type ViewerContext,
} from "../viewerContext.svelte";

const defaultStroke = "rgba(0, 255, 0, 1)";
const fillStyle = "rgba(255, 255, 255, 0.6)";

export type PointToolOptions = {
    canEdit: boolean;
    adapter: PointAdapter;
    label?: string;
    pointStyle?: PointMarkerStyle;
    radius?: number;
    color?: string;
    /** When provided, empty click / slot shortcuts use placePointAt. */
    getActiveSlot?: () => number;
    setActiveSlot?: (index: number) => void;
    /** Keyboard shortcuts into fixed slots (handled in keydown). */
    slotKeys?: readonly { index: number; key: string }[];
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
    }

    /** No-op: kept so MainViewer overlay cleanup can call it unconditionally. */
    destroy() {}

    private get points(): PointList {
        return this.options.adapter.getPoints();
    }

    private commit(points: PointList) {
        this.options.adapter.setPoints(points);
    }

    /**
     * Place/replace at image coords under the viewer cursor (e.g. keyboard shortcut).
     * When `slot` is given, always writes that slot via `placePointAt` (used by
     * `slotKeys`); otherwise defers to `getActiveSlot()` when defined, else the
     * schema-driven `placePoint` (cardinality/registration fill-first-null).
     */
    placeAtCursor(viewerContext: ViewerContext, cursor: Position2D, slot?: number) {
        if (!this.options.canEdit) return;
        const position = viewerContext.viewerToImageCoordinates(cursor);
        const before = this.points;
        const targetSlot = slot ?? this.options.getActiveSlot?.();
        const after =
            targetSlot !== undefined
                ? placePointAt(
                      before,
                      targetSlot,
                      position,
                      this.placeIndexOptions(viewerContext),
                  )
                : placePoint(
                      before,
                      position,
                      this.options.adapter.analysis.cardinality,
                      this.options.adapter.analysis.registrationMode,
                      this.placeIndexOptions(viewerContext),
                  );
        let newIndex = targetSlot;
        if (newIndex === undefined) {
            newIndex = after.findIndex(
                (p, i) => p && (!before[i] || before[i] !== p),
            );
            if (newIndex < 0) newIndex = Math.max(0, after.length - 1);
        }
        this.commit(after);
        this.beginDrag(viewerContext, newIndex);
        this.options.setActiveSlot?.(newIndex);
    }

    /**
     * Index for OCT: numbered on B-scans, explicit `null` on enface `*_proj`,
     * omitted on plain 2D (enface and volume share the same PublicID).
     */
    private placeIndexOptions(
        viewerContext: ViewerContext,
    ): { index: number | null } | undefined {
        const { image } = viewerContext;
        if (image.is3D) {
            return { index: viewerContext.index };
        }
        if (image.image_id.endsWith("_proj")) {
            return { index: null };
        }
        return undefined;
    }

    /** Whether this point should paint/hit on the current viewer. */
    private visibleOnSlice(
        pt: ImagePoint,
        viewerContext: ViewerContext,
    ): boolean {
        const { image } = viewerContext;
        if (image.is3D) {
            return (
                typeof pt.index === "number" &&
                pt.index === viewerContext.index
            );
        }
        if (image.image_id.endsWith("_proj")) {
            // Enface: only points tagged with null (or legacy missing index).
            return pt.index == null;
        }
        // Plain 2D: hide volume slice points if present in the same list.
        return typeof pt.index !== "number";
    }

    private beginDrag(viewerContext: ViewerContext, index: number) {
        this.activePointIndex = index;
        this.hoverPointIndex = index;
        viewerContext.claimCursor("grabbing", CursorPriority.Drag);
    }

    private endDrag(viewerContext: ViewerContext, cursor: Position2D) {
        const wasDragging = this.activePointIndex !== undefined;
        this.activePointIndex = undefined;
        this.hoverPointIndex = this.findHit(cursor, viewerContext);
        if (wasDragging) viewerContext.resetCursor();
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext } = e;

        if (
            this.options.adapter.analysis.registrationMode &&
            !this.options.getActiveSlot &&
            event.key >= "0" &&
            event.key <= "9"
        ) {
            const index = parseInt(event.key, 10) - 1;
            const point = this.points[index];
            if (point) {
                if (typeof point.index === "number") {
                    viewerContext.setIndex(point.index);
                }
                const w = viewerContext.viewerSize.width;
                const w_image = viewerContext.image.width;
                viewerContext.focusPoint(point.x, point.y, (1 * w_image) / w);
            }
        }
    }

    keydown(e: ViewerEvent<KeyboardEvent>) {
        if (!this.options.canEdit) return;
        const { event, viewerContext, cursor } = e;

        if (!event.repeat && this.options.slotKeys) {
            const match = this.options.slotKeys.find(
                (s) => s.key.toLowerCase() === event.key.toLowerCase(),
            );
            if (match) {
                this.options.setActiveSlot?.(match.index);
                this.placeAtCursor(viewerContext, cursor, match.index);
                return;
            }
        }

        if (event.key.toLowerCase() !== "c") return;

        const index = this.activePointIndex ?? this.hoverPointIndex;
        if (index === undefined) return;
        const point = this.points[index];
        if (!point) return;

        const extra = this.options.adapter.analysis.enumExtras[0];
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
                this.beginDrag(viewerContext, hit);
                this.options.setActiveSlot?.(hit);
                return;
            }

            this.placeAtCursor(viewerContext, cursor);
        }
    }

    pointerup(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = pointerEvent;
        if (event.shiftKey) return;

        if (!this.options.canEdit) {
            this.endDrag(viewerContext, cursor);
            return;
        }

        if (event.button === 2) {
            const hit = this.findHit(cursor, viewerContext);
            if (hit !== undefined) {
                this.commit(
                    deletePointAt(
                        this.points,
                        hit,
                        this.options.adapter.analysis.registrationMode,
                    ),
                );
            }
        }

        this.endDrag(viewerContext, cursor);
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        const { cursor, viewerContext } = e;

        if (this.activePointIndex !== undefined && this.options.canEdit) {
            const position = viewerContext.viewerToImageCoordinates(cursor);
            this.commit(
                movePointAt(this.points, this.activePointIndex, position),
            );
            viewerContext.claimCursor("grabbing", CursorPriority.Drag);
        } else {
            this.hoverPointIndex = this.findHit(cursor, viewerContext);
        }
    }

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        const points = this.points;
        const highlightIndex = this.activePointIndex ?? this.hoverPointIndex;
        const activeSlot = this.options.getActiveSlot?.();

        const { context2D } = viewerContext;
        const strokeStyle = this.color;

        context2D.strokeStyle = strokeStyle;
        context2D.fillStyle = strokeStyle;
        context2D.font = "16px sans-serif";

        const r = this.radius;
        const { analysis, slotLabels } = this.options.adapter;
        const showIndex =
            analysis.cardinality === "list" || analysis.registrationMode;

        for (const [index, pt] of points.entries()) {
            if (!pt) continue;
            if (!this.visibleOnSlice(pt, viewerContext)) continue;
            context2D.lineWidth = index === activeSlot ? 2 : 1.25;
            const p = viewerContext.imageToViewerCoordinates(pt);
            this.strokeMarker(context2D, p, r);

            let label = slotLabels?.[index];
            if (!label) {
                label = showIndex ? `${index + 1}` : this.name;
                const extraLabel = this.extraLabel(pt);
                if (extraLabel) {
                    label = showIndex
                        ? `${index + 1}:${extraLabel}`
                        : extraLabel;
                }
            }
            if (label) {
                context2D.fillText(label, p.x + r, p.y + r + 12);
            }
        }

        context2D.fillStyle = fillStyle;
        if (highlightIndex !== undefined) {
            const highlightPoint = points[highlightIndex];
            if (
                highlightPoint &&
                this.visibleOnSlice(highlightPoint, viewerContext)
            ) {
                const p =
                    viewerContext.imageToViewerCoordinates(highlightPoint);
                this.fillMarker(context2D, p, r);
            }
        }
        if (this.activePointIndex !== undefined) {
            viewerContext.claimCursor("grabbing", CursorPriority.Drag);
        }
    }

    private extraLabel(pt: ImagePoint): string | undefined {
        // Prefer schema-declared enum extras (stable order), then any other
        // string property on the point (free-text extras).
        for (const extra of this.options.adapter.analysis.enumExtras) {
            const v = pt[extra.key];
            if (typeof v === "string" && v.length > 0) return v;
        }
        for (const [key, v] of Object.entries(pt)) {
            if (key === "x" || key === "y" || key === "index") continue;
            if (
                this.options.adapter.analysis.enumExtras.some(
                    (e) => e.key === key,
                )
            ) {
                continue;
            }
            if (typeof v === "string" && v.length > 0) return v;
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
            if (!this.visibleOnSlice(value, viewerContext)) continue;
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
