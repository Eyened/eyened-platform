import type { Scale } from "$lib/layers/imageScale";
import type { Registration } from "$lib/registration/registration.svelte";
import type { Overlay } from "../viewer-utils";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";
import { cased } from "./casing";
import { ETDRS_CIRCLES, type CircleSize } from "./etdrsCircles";

/** The ETDRS circle at the shared pointer, sized from this viewport's image scale; it hides the system cursor while it shows. */
export class EtdrsCircleOverlay implements Overlay {
    constructor(
        private readonly registration: Registration,
        private readonly size: () => CircleSize,
        private readonly scale: () => Scale | null,
    ) {}

    repaint(viewerContext: ViewerContext) {
        const scale = this.scale();
        const cursor = this.registration.getPosition(
            viewerContext.image.image_id,
        );
        if (!scale || !cursor) return;
        // The radius in µm, then in image pixels on each axis.
        const um = (ETDRS_CIRCLES[this.size()] / 2) * 1000;
        const centre = viewerContext.imageToViewerCoordinates(cursor);
        const edgeX = viewerContext.imageToViewerCoordinates({
            x: cursor.x + um / scale.x,
            y: cursor.y,
        });
        const edgeY = viewerContext.imageToViewerCoordinates({
            x: cursor.x,
            y: cursor.y + um / scale.y,
        });
        const ctx = viewerContext.context2D;
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(255, 255, 255, 1)";
        ctx.beginPath();
        ctx.ellipse(
            centre.x,
            centre.y,
            Math.hypot(edgeX.x - centre.x, edgeX.y - centre.y),
            Math.hypot(edgeY.x - centre.x, edgeY.y - centre.y),
            0,
            0,
            2 * Math.PI,
        );
        cased(ctx, () => ctx.stroke());
        viewerContext.claimCursor("none", CursorPriority.Hide);
    }
}
