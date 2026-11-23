import { Matrix } from "$lib/matrix";
import type { Position2D } from "$lib/types";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import { segToImageMatrix } from "$lib/webgl/segmentationProjection";
import type { RenderTarget } from "$lib/webgl/types";
import { sizeKey } from "$lib/workspace/paint";
import type { Workspace } from "$lib/workspace/workspace.svelte";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";

export type DrawingMode = "erase" | "paint";

/** What a Draw tool reads from the workspace. */
export type PaintView = Pick<Workspace, "paint" | "remove" | "setSize">;

export interface DrawToolDeps {
    viewerContext: ViewerContext;
    segmentationContext: SegmentationContext;
    view: PaintView;
    /** Tells the grader a stroke could not be drawn; null when a stroke worked. */
    report: (message: string | null) => void;
}

export abstract class SegmentationTool implements Overlay {
    paintColor = "rgba(200, 255, 200, 0.5)";
    eraseColor = "rgba(255, 200, 200, 0.5)";
    fillColor = "rgba(255, 255, 255, 0.4)";

    currentPoints: Position2D[] | undefined;
    lastPosition: Position2D | undefined;
    syncing: boolean = false;
    /** Fixed when a stroke starts, so its preview and its write agree. */
    protected stroke: { mode: DrawingMode; size: number } | undefined;
    /** `lockScroll` before the stroke, put back when it ends. */
    private scrollBefore: boolean | undefined;

    protected readonly viewerContext: ViewerContext;
    protected readonly segmentationContext: SegmentationContext;
    protected readonly view: PaintView;
    protected readonly report: (message: string | null) => void;

    constructor(deps: DrawToolDeps) {
        this.viewerContext = deps.viewerContext;
        this.segmentationContext = deps.segmentationContext;
        this.view = deps.view;
        this.report = deps.report;
    }

    /** The mode a stroke started now would have. */
    protected abstract nextMode(): DrawingMode;

    abstract executeDraw(
        ctx: CanvasRenderingContext2D,
        viewerContext: ViewerContext,
    ): void;

    get mode(): DrawingMode {
        return this.stroke?.mode ?? this.nextMode();
    }

    /** The brush size in image pixels for this viewer's image kind. */
    get size(): number {
        return (
            this.stroke?.size ??
            this.view.paint[sizeKey(this.viewerContext.image)]
        );
    }

    get drawingColor(): string {
        return this.mode === "paint" ? this.paintColor : this.eraseColor;
    }

    /** A stroke is written to the slice shown when it ends, so the wheel and arrows don't step slices during one. */
    protected setDrawing(on: boolean): void {
        this.segmentationContext.isDrawing = on;
        if (on && this.scrollBefore === undefined) {
            this.scrollBefore = this.viewerContext.lockScroll;
            this.viewerContext.lockScroll = true;
        } else if (!on && this.scrollBefore !== undefined) {
            this.viewerContext.lockScroll = this.scrollBefore;
            this.scrollBefore = undefined;
        }
    }

    protected segToImageMatrix(): Matrix {
        const segmentation =
            this.segmentationContext.segmentationItem?.segmentation;
        if (!segmentation) {
            return Matrix.identity;
        }
        return segToImageMatrix(segmentation);
    }

    protected segmentationViewerTransform(): Matrix {
        return this.viewerContext.imageViewerTransform.multiply(
            this.segToImageMatrix(),
        );
    }

    /** Viewer events carry image-space position; convert to segmentation pixels. */
    protected eventToSegmentation(
        e: ViewerEvent<PointerEvent | KeyboardEvent | WheelEvent | MouseEvent>,
    ): Position2D {
        return this.segToImageMatrix().inverse.apply(e.position);
    }

    protected segmentationToViewer(pixel: Position2D): Position2D {
        return this.segmentationViewerTransform().apply(pixel);
    }

    /**
     * Brush radius is defined in image pixels; convert to segmentation radii at centerSeg.
     * centerSeg must be in segmentation coordinates.
     */
    protected imageBrushRadiiToSegmentation(centerSeg: Position2D): {
        rx: number;
        ry: number;
    } {
        const segToImage = this.segToImageMatrix();
        const imageToSeg = segToImage.inverse;
        const imageCenter = segToImage.apply(centerSeg);
        const r = this.size;
        const aspect = this.viewerContext.aspectRatio;
        const px = imageToSeg.apply({ x: imageCenter.x + r, y: imageCenter.y });
        const py = imageToSeg.apply({
            x: imageCenter.x,
            y: imageCenter.y + r * aspect,
        });
        return {
            rx: Math.hypot(px.x - centerSeg.x, px.y - centerSeg.y),
            ry: Math.hypot(py.x - centerSeg.x, py.y - centerSeg.y),
        };
    }

    keydown(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext } = e;
        if (event.key === "Escape") {
            if (this.stroke) this.cancel(viewerContext);
            return;
        }
        if (
            event.code !== "Space" ||
            event.ctrlKey ||
            event.metaKey ||
            event.altKey
        )
            return;
        event.preventDefault();
        // Hold Space acts at the pointer, so only in the viewport the pointer is over.
        if (
            event.repeat ||
            this.stroke ||
            !viewerContext.active ||
            !this.lastPosition
        )
            return;
        this.startDraw(viewerContext);
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        if (e.event.code === "Space") this.endDraw(e.viewerContext);
    }

    /** A pen leaving the screen keeps what was drawn; undo takes it back. */
    pointercancel(e: ViewerEvent<PointerEvent>) {
        this.endDraw(e.viewerContext);
    }

    /** Losing focus keeps what was drawn; undo takes it back. */
    blur(e: ViewerEvent<FocusEvent>) {
        this.endDraw(e.viewerContext);
    }

    startDraw(_viewerContext: ViewerContext) {
        this.stroke = { mode: this.nextMode(), size: this.size };
        this.currentPoints = [this.lastPosition!];
        this.setDrawing(true);
    }

    /** Esc: the stroke is dropped and nothing is written. */
    cancel(_viewerContext: ViewerContext) {
        this.currentPoints = undefined;
        this.stroke = undefined;
        this.setDrawing(false);
    }

    endDraw(viewerContext: ViewerContext) {
        this.setDrawing(false);
        if (this.currentPoints) {
            this.syncing = true;
            const ctx = this.segmentationContext.getCtx();
            this.executeDraw(ctx, viewerContext);
            // Named now: the selection may change before the draw fails.
            const name =
                this.segmentationContext.segmentationItem?.segmentation.feature
                    .name ?? "the segmentation";
            this.segmentationContext
                .draw(ctx, this.mode, viewerContext.index)
                .then(() => this.report(null))
                .catch((error) => {
                    console.error(error);
                    this.report(`Couldn't draw on ${name}`);
                })
                .finally(() => (this.syncing = false));
            this.currentPoints = undefined;
        }
        this.stroke = undefined;
    }

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        if (this.syncing) {
            viewerContext.claimCursor("wait", CursorPriority.Busy);
        }
    }
}

/** A dark casing under overlay lines keeps them at 3:1 against light and dark retina. */
const CASING = "rgba(0, 0, 0, 0.75)";

/** Strokes `path` 1 px in `color` over a 3 px dark casing. */
export function casedStroke(
    ctx: CanvasRenderingContext2D,
    path: Path2D,
    color: string,
    dash: number[] = [],
): void {
    ctx.save();
    ctx.setLineDash(dash);
    ctx.lineWidth = 3;
    ctx.strokeStyle = CASING;
    ctx.stroke(path);
    ctx.lineWidth = 1;
    ctx.strokeStyle = color;
    ctx.stroke(path);
    ctx.restore();
}
