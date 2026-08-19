import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { ImageBox } from "$lib/viewer-window/panelSegmentation/segmentationRegion";
import { imageBoxFromCorners } from "$lib/viewer-window/panelSegmentation/segmentationRegion";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

export class SegmentationRegionTool implements Overlay {
    private startImagePos: { x: number; y: number } | undefined;
    draftBox: ImageBox | undefined = undefined;

    constructor(
        private readonly viewerContext: ViewerContext,
        private readonly segmentationContext: SegmentationContext,
    ) {}

    deactivate() {
        this.startImagePos = undefined;
        this.draftBox = undefined;
        this.segmentationContext.regionToolActive = false;
    }

    pointerdown(e: ViewerEvent<PointerEvent>) {
        const { event, position, modifiers } = e;
        if (event.button !== 0 || modifiers.alt || modifiers.shift) return;
        this.startImagePos = { x: position.x, y: position.y };
        this.draftBox = imageBoxFromCorners(
            this.startImagePos,
            this.startImagePos,
        );
    }

    pointermove(e: ViewerEvent<PointerEvent>) {
        if (!this.startImagePos) return;
        this.draftBox = imageBoxFromCorners(this.startImagePos, e.position);
    }

    pointerup(e: ViewerEvent<PointerEvent>) {
        if (!this.startImagePos) return;
        const box = imageBoxFromCorners(this.startImagePos, e.position);
        this.startImagePos = undefined;
        this.draftBox = undefined;

        const w = box.x1 - box.x0;
        const h = box.y1 - box.y0;
        if (w < 2 || h < 2) {
            return;
        }

        this.segmentationContext.pendingRegionBox = box;
        this.deactivate();
    }

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        if (!this.draftBox) return;
        const ctx = viewerContext.context2D;
        const p0 = viewerContext.imageToViewerCoordinates({
            x: this.draftBox.x0,
            y: this.draftBox.y0,
        });
        const p1 = viewerContext.imageToViewerCoordinates({
            x: this.draftBox.x1,
            y: this.draftBox.y1,
        });
        const left = Math.min(p0.x, p1.x);
        const top = Math.min(p0.y, p1.y);
        const w = Math.abs(p1.x - p0.x);
        const h = Math.abs(p1.y - p0.y);

        ctx.save();
        ctx.strokeStyle = "rgba(100, 200, 255, 0.95)";
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.strokeRect(left, top, w, h);
        ctx.setLineDash([]);
        ctx.restore();
    }
}
