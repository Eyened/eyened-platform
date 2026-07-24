import { formAnnotations } from "$lib/data";
import type { Position2D } from "$lib/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import type { RenderTarget } from "$lib/webgl/types";

const strokeStyleFovea = "rgba(255, 255, 0, 1)";
const strokeStyleDisc = "rgba(0, 255, 255, 1)";
const radius = 6;

/**
 * Paints both ETDRS landmarks (fovea + disc_edge) from the live FormAnnotation
 * store. Used while edit mode is active so the non-armed landmark stays visible.
 */
export class ETDRSLandmarksOverlay implements Overlay {
    name = "ETDRS landmarks";

    constructor(
        private readonly annotationId: number,
        private readonly getArmedField: () => "fovea" | "disc_edge" | undefined,
    ) {}

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        const annotation = formAnnotations.get(this.annotationId);
        const form_data = annotation?.form_data as
            | { fovea?: Position2D; disc_edge?: Position2D }
            | undefined;
        if (!form_data) return;

        const ctx = viewerContext.context2D;
        ctx.lineWidth = 1;
        ctx.fillStyle = "white";
        ctx.font = "14px sans-serif";

        const armed = this.getArmedField();
        this.paintMarker(
            form_data.fovea,
            ctx,
            viewerContext,
            strokeStyleFovea,
            "fovea",
            armed === "fovea",
        );
        this.paintMarker(
            form_data.disc_edge,
            ctx,
            viewerContext,
            strokeStyleDisc,
            "disc",
            armed === "disc_edge",
        );
    }

    private paintMarker(
        position: Position2D | undefined,
        ctx: CanvasRenderingContext2D,
        viewerContext: ViewerContext,
        strokeStyle: string,
        label: string,
        armed: boolean,
    ) {
        if (!position) return;
        ctx.strokeStyle = strokeStyle;
        ctx.lineWidth = armed ? 2 : 1;
        const p = viewerContext.imageToViewerCoordinates(position);
        ctx.strokeRect(p.x - radius, p.y - radius, 2 * radius, 2 * radius);
        ctx.fillStyle = strokeStyle;
        ctx.fillText(label, p.x + radius + 2, p.y + radius + 12);
    }
}
