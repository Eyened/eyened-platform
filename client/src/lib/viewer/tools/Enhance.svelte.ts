import { ProbabilityMask } from "$lib/webgl/mask.svelte";
import type { ViewerContext } from "../viewerContext.svelte";
import { BrushTool } from "./Brush";
import type { DrawingMode, DrawToolDeps } from "./segmentation";

/** Raises a probability segmentation under the brush while held, or lowers it with X. */
export class EnhanceTool extends BrushTool {
    private drawInterval: ReturnType<typeof setInterval> | undefined;

    constructor(deps: DrawToolDeps) {
        super(deps, "paint");
    }

    protected nextMode(): DrawingMode {
        return this.view.remove ? "erase" : "paint";
    }

    startDraw(viewerContext: ViewerContext) {
        const mask =
            this.segmentationContext.segmentationItem?.getSegmentationState(
                viewerContext.index,
                true,
            )?.mask;
        // The options bar already says why when the target is not a probability segmentation.
        if (!(mask instanceof ProbabilityMask)) return;
        this.stroke = { mode: this.nextMode(), size: this.size };
        this.setDrawing(true);
        this.drawInterval = setInterval(() => {
            if (!this.lastPosition || !this.stroke) return;
            const { rx, ry } = this.imageBrushRadiiToSegmentation(
                this.lastPosition,
            );
            mask.drawEnhance({
                radiusX: rx,
                radiusY: ry,
                hardness: this.view.paint.hardness,
                pressure: this.view.paint.pressure,
                erase: this.stroke.mode === "erase",
                point: this.lastPosition,
            });
        }, 1000 / 30); // 30 times per second
    }

    endDraw(viewerContext: ViewerContext) {
        this.finish(viewerContext, false);
    }

    /** Enhance writes while held, so Esc commits the stroke and undoes it at once. */
    cancel(viewerContext: ViewerContext) {
        this.finish(viewerContext, true);
    }

    private finish(viewerContext: ViewerContext, undo: boolean) {
        this.setDrawing(false);
        this.stroke = undefined;
        if (!this.drawInterval) return;
        clearInterval(this.drawInterval);
        this.drawInterval = undefined;
        const item = this.segmentationContext.segmentationItem;
        if (!item) return;
        const index = viewerContext.index;
        item.draw(index, null as never, {})
            .then(() => (undo ? item.undo(index) : undefined))
            .catch((error) => {
                console.error(error);
                this.report(
                    "Error drawing on segmentation. Check console for details.",
                );
            });
    }
}
