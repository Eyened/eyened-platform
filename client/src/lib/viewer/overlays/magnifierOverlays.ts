import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { cased } from "./casing";

/** Copies this viewer's part of the shared WebGL canvas under its 2D drawing, so the panel covers what lies below it. */
export class MagnifierCopy implements Overlay {
    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        const { context2D, canvas2D } = viewerContext;
        const gl = viewerContext.image.webgl.gl.canvas as HTMLCanvasElement;
        const { left, bottom, width, height } = renderTarget;
        context2D.save();
        context2D.globalCompositeOperation = "destination-over";
        context2D.drawImage(
            gl,
            left,
            gl.height - bottom - height,
            width,
            height,
            0,
            0,
            canvas2D.width,
            canvas2D.height,
        );
        context2D.restore();
    }
}

const ARM_PX = 16;
const GAP_PX = 4;

/** The centre mark: a thin cross with a gap at the centre and, with a brush armed, the brush circle at this viewer's zoom. */
export class MagnifierMark implements Overlay {
    constructor(
        private readonly brush: () => {
            /** In image px. */
            radius: number;
            dashed: boolean;
        } | null,
    ) {}

    repaint(viewerContext: ViewerContext) {
        const ctx = viewerContext.context2D;
        const x = Math.floor(viewerContext.viewerSize.width / 2) + 0.5;
        const y = Math.floor(viewerContext.viewerSize.height / 2) + 0.5;
        const brush = this.brush();
        const r = brush
            ? brush.radius * viewerContext.imageViewerTransform.a
            : 0;
        // The arms stop inside the circle.
        const arm = r > 0 ? Math.min(ARM_PX, r - 3) : ARM_PX;
        ctx.save();
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
        if (arm > GAP_PX)
            cased(ctx, () => {
                ctx.beginPath();
                ctx.moveTo(x - arm, y);
                ctx.lineTo(x - GAP_PX, y);
                ctx.moveTo(x + GAP_PX, y);
                ctx.lineTo(x + arm, y);
                ctx.moveTo(x, y - arm);
                ctx.lineTo(x, y - GAP_PX);
                ctx.moveTo(x, y + GAP_PX);
                ctx.lineTo(x, y + arm);
                ctx.stroke();
            });
        if (brush && r > 0) {
            ctx.setLineDash(brush.dashed ? [4, 4] : []);
            cased(ctx, () => {
                ctx.beginPath();
                ctx.arc(x, y, r, 0, 2 * Math.PI);
                ctx.stroke();
            });
        }
        ctx.restore();
    }
}
