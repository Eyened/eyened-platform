import type { PointMarkerStyle } from "$lib/config/clientDefaults";
import {
    cycleEnumExtra,
    deletePointAt,
    movePointAt,
    placePoint,
    placePointAt,
} from "$lib/forms/pointMutations";
import type {
    ImagePoint,
    PointCardinality,
    PointCoordinateSpace,
    PointList,
} from "$lib/forms/pointSchema";
import { canPlaceOnViewer } from "$lib/forms/pointSchema";
import type { Position2D } from "$lib/types";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay, ToolName, ViewerEvent } from "../viewer-utils";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";
import { toast } from "svelte-sonner";

const defaultStroke = "rgba(0, 255, 0, 1)";
const fillStyle = "rgba(255, 255, 255, 0.6)";

export type PointToolOptions = {
    canEdit?: boolean;
    label?: string;
    pointStyle?: PointMarkerStyle;
    radius?: number;
    color?: string;
    /** Default `list`. `single` → empty click replaces the sole point. */
    cardinality?: PointCardinality;
    /**
     * Registration lists: empty click fills first null; mid-list delete → null.
     * Ignored when `placementIndex` is set (fixed-slot / ETDRS mode).
     */
    sparse?: boolean;
    /**
     * When set, gates placement and index injection.
     * Omit for legacy callers (allow all viewers; inject index on 3D / `_proj`).
     */
    coordinateSpace?: PointCoordinateSpace;
    slotLabels?: readonly string[];
    /** Keyboard shortcut → place into that index (also sets placementIndex). */
    slotKeys?: readonly { index: number; key: string }[];
    enumExtras?: { key: string; values: readonly string[] }[];
    /**
     * Fired after every local mutation of `points` (including drag moves).
     * Use for in-memory / UI sync. Prefer `onPersist` for server writes.
     */
    onChange?: (points: PointList) => void;
    /**
     * Fired when an edit is finished (pointerup after place/drag, delete, enum).
     * Use for server persistence — not called on every pointermove.
     */
    onPersist?: (points: PointList) => void;
};

/**
 * Viewer overlay that edits an in-memory point list.
 * FormAnnotation / schema storage stay outside — sync via `onChange` + assigning `points`.
 */
export class PointTool implements Overlay {
    /** Observable point list. Assign to load; mutations go through tool methods. */
    points: PointList = $state([]);

    /**
     * When set (ETDRS), empty-click placement always writes this index and
     * stays there until another point is clicked/dragged (or set externally).
     * When `undefined` (Registration / free lists), empty click appends /
     * fill-first-null and never latches an index.
     */
    placementIndex: number | undefined = $state(undefined);

    private activePointIndex: number | undefined;
    private hoverPointIndex: number | undefined;

    toolName: ToolName = "point";
    name: string = "Point";

    private readonly canEdit: boolean;
    private readonly pointStyle: PointMarkerStyle;
    private readonly radius: number;
    private readonly color: string;
    private readonly cardinality: PointCardinality;
    private readonly sparse: boolean;
    private readonly coordinateSpace: PointCoordinateSpace | undefined;
    private readonly slotLabels: readonly string[] | undefined;
    private readonly slotKeys:
        | readonly { index: number; key: string }[]
        | undefined;
    private readonly enumExtras: { key: string; values: readonly string[] }[];
    private readonly onChange: ((points: PointList) => void) | undefined;
    private readonly onPersist: ((points: PointList) => void) | undefined;
    /** True while a place/drag gesture may need a persist on pointerup. */
    private persistOnRelease = false;

    constructor(options: PointToolOptions = {}) {
        this.canEdit = options.canEdit ?? true;
        this.pointStyle = options.pointStyle ?? "circle";
        this.radius = options.radius ?? 16;
        this.color = options.color ?? defaultStroke;
        this.name = options.label || "Point";
        this.cardinality = options.cardinality ?? "list";
        this.sparse = options.sparse ?? false;
        this.coordinateSpace = options.coordinateSpace;
        this.slotLabels = options.slotLabels;
        this.slotKeys = options.slotKeys;
        this.enumExtras = options.enumExtras ?? [];
        this.onChange = options.onChange;
        this.onPersist = options.onPersist;
    }

    destroy() {}

    /** Local render + optional live UI sync; does not hit the server. */
    private setPoints(next: PointList, opts?: { persist?: boolean }) {
        this.points = next;
        this.onChange?.(next);
        if (opts?.persist) {
            this.onPersist?.(next);
            this.persistOnRelease = false;
        }
    }

    placeAtCursor(
        viewerContext: ViewerContext,
        cursor: Position2D,
        slot?: number,
    ) {
        if (!this.canEdit) return;
        if (this.coordinateSpace) {
            const gate = canPlaceOnViewer(
                this.coordinateSpace,
                viewerContext.image,
            );
            if (!gate.ok) {
                toast.warning(gate.message);
                return;
            }
        }
        const position = viewerContext.viewerToImageCoordinates(cursor);
        const before = this.points;
        const targetSlot = slot ?? this.placementIndex;
        const indexOpts = this.placeIndexOptions(viewerContext);

        const after =
            targetSlot !== undefined
                ? placePointAt(before, targetSlot, position, indexOpts)
                : placePoint(
                      before,
                      position,
                      this.cardinality,
                      this.sparse,
                      indexOpts,
                  );

        let newIndex = targetSlot;
        if (newIndex === undefined) {
            newIndex = after.findIndex(
                (p, i) => p && (!before[i] || before[i] !== p),
            );
            if (newIndex < 0) newIndex = Math.max(0, after.length - 1);
        }

        this.setPoints(after);
        this.persistOnRelease = true;
        // Restricted mode (ETDRS): keep sticking to the placement index.
        // Unrestricted (Registration): leave placementIndex undefined so the
        // next empty click appends instead of rewriting the last point.
        if (this.placementIndex !== undefined && targetSlot !== undefined) {
            this.placementIndex = targetSlot;
        }
        this.beginDrag(viewerContext, newIndex);
    }

    private placeIndexOptions(
        viewerContext: ViewerContext,
    ): { index: number | null } | undefined {
        // enface2d fields never store index (even if somehow on a volume).
        if (this.coordinateSpace === "enface2d") return undefined;
        const { image } = viewerContext;
        if (image.is3D) return { index: viewerContext.index };
        if (image.image_id.endsWith("_proj")) return { index: null };
        return undefined;
    }

    private visibleOnSlice(
        pt: ImagePoint,
        viewerContext: ViewerContext,
    ): boolean {
        const { image } = viewerContext;
        if (image.is3D) {
            return (
                typeof pt.index === "number" && pt.index === viewerContext.index
            );
        }
        if (image.image_id.endsWith("_proj")) {
            return pt.index == null;
        }
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
        if (this.persistOnRelease) {
            this.onPersist?.(this.points);
            this.persistOnRelease = false;
        }
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext, cursor } = e;

        if (
            this.slotKeys?.some(
                (s) => s.key.toLowerCase() === event.key.toLowerCase(),
            )
        ) {
            this.endDrag(viewerContext, cursor);
        }

        if (
            this.sparse &&
            this.placementIndex === undefined &&
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
        if (!this.canEdit) return;
        const { event, viewerContext, cursor } = e;

        if (!event.repeat && this.slotKeys) {
            const match = this.slotKeys.find(
                (s) => s.key.toLowerCase() === event.key.toLowerCase(),
            );
            if (match) {
                this.placementIndex = match.index;
                this.placeAtCursor(viewerContext, cursor, match.index);
                return;
            }
        }

        if (event.key.toLowerCase() !== "c") return;
        const index = this.activePointIndex ?? this.hoverPointIndex;
        if (index === undefined) return;
        const point = this.points[index];
        if (!point) return;
        const extra = this.enumExtras[0];
        if (!extra) return;
        const points = [...this.points];
        points[index] = cycleEnumExtra(point, extra.key, extra.values);
        this.setPoints(points, { persist: true });
    }

    pointerdown(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = pointerEvent;
        if (event.shiftKey) return;
        if (!this.canEdit) return;

        if (event.button === 0) {
            const hit = this.findHit(cursor, viewerContext);
            if (hit !== undefined) {
                // Only switch the restricted index when one is already set
                // (ETDRS). Registration must not latch onto the hit index.
                if (this.placementIndex !== undefined) {
                    this.placementIndex = hit;
                }
                this.persistOnRelease = true;
                this.beginDrag(viewerContext, hit);
                return;
            }
            this.placeAtCursor(viewerContext, cursor);
        }
    }

    pointerup(pointerEvent: ViewerEvent<PointerEvent>) {
        const { event, viewerContext, cursor } = pointerEvent;
        if (event.shiftKey) return;

        if (!this.canEdit) {
            this.endDrag(viewerContext, cursor);
            return;
        }

        if (event.button === 2) {
            const hit = this.findHit(cursor, viewerContext);
            if (hit !== undefined) {
                const useNullDelete =
                    this.sparse || this.placementIndex !== undefined;
                this.setPoints(deletePointAt(this.points, hit, useNullDelete), {
                    persist: true,
                });
            }
        }

        this.endDrag(viewerContext, cursor);
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        const { cursor, viewerContext } = e;

        if (this.activePointIndex !== undefined && this.canEdit) {
            const position = viewerContext.viewerToImageCoordinates(cursor);
            // Live render / local store only — persist on pointerup.
            this.setPoints(
                movePointAt(this.points, this.activePointIndex, position),
            );
            this.persistOnRelease = true;
            viewerContext.claimCursor("grabbing", CursorPriority.Drag);
        } else {
            this.hoverPointIndex = this.findHit(cursor, viewerContext);
        }
    }

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        const points = this.points;
        const highlightIndex = this.activePointIndex ?? this.hoverPointIndex;
        const { context2D } = viewerContext;

        context2D.strokeStyle = this.color;
        context2D.fillStyle = this.color;
        context2D.font = "16px sans-serif";

        const r = this.radius;
        const showIndex = this.cardinality === "list" || this.sparse;

        for (const [index, pt] of points.entries()) {
            if (!pt) continue;
            if (!this.visibleOnSlice(pt, viewerContext)) continue;
            context2D.lineWidth =
                this.placementIndex !== undefined &&
                index === this.placementIndex
                    ? 2
                    : 1.25;
            const p = viewerContext.imageToViewerCoordinates(pt);
            this.strokeMarker(context2D, p, r);

            let label = this.slotLabels?.[index];
            if (!label) {
                const extraLabel = this.extraLabel(pt);
                if (showIndex) {
                    label = extraLabel
                        ? `${index + 1}:${extraLabel}`
                        : `${index + 1}`;
                } else {
                    // Single: extra if set, else field title (this.name).
                    label = extraLabel ?? this.name;
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
        for (const extra of this.enumExtras) {
            const v = pt[extra.key];
            if (typeof v === "string" && v.length > 0) return v;
        }
        for (const [key, v] of Object.entries(pt)) {
            if (key === "x" || key === "y" || key === "index") continue;
            if (this.enumExtras.some((e) => e.key === key)) continue;
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
