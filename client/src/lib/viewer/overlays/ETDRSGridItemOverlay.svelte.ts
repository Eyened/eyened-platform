import { formAnnotations } from "$lib/data";
import type { Registration } from "$lib/registration/registration.svelte";
import type { Position, Position2D } from "$lib/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { cased, casedText } from "./casing";
import { ETDRS_CIRCLES } from "./etdrsCircles";

// Carbon magenta 40, over a darker casing: on a bright fundus the default casing leaves it under 3:1.
const AI_COLOUR = "#ff7eb6";
const AI_CASING = "rgba(0, 0, 0, 0.8)";

/** Place ETDRS's cross on the fovea and the disc edge. */
export const ETDRS_LANDMARK_COLOUR = "rgba(0, 255, 0, 1)";

export type etdrsGridType = {
    image_id: string;
    form_data: {
        fovea: { x: number; y: number };
        disc_edge: { x: number; y: number };
    };
};

/** Live FormAnnotation from the store, or a static snapshot: the AI grid, which also rings its two points. */
export type ETDRSGridSource =
    | { kind: "annotation"; id: number }
    | { kind: "snapshot"; data: etdrsGridType };

/** A grid's stored points; either may be missing while it is being placed. */
export type GridData = { fovea?: Position2D; disc_edge?: Position2D };

/**
 * ETDRS landmarks are always en-face 2D `(x, y)`. An OCT volume's en-face plane is `${id}_proj`, so map from that node and never through OCTToProj, which remaps `index → y`.
 * A plain CF id has no proj edge and stays as is.
 */
function enfaceSourceId(registration: Registration, gridImageId: string): string {
    if (gridImageId.endsWith("_proj")) return gridImageId;
    const projId = `${gridImageId}_proj`;
    return registration.getRegistrationItem(gridImageId, projId)
        ? projId
        : gridImageId;
}

/** A grid's fovea and disc edge in another image's pixels, through registration; null for a point that is missing or doesn't map. */
export function gridPointsIn(
    registration: Registration,
    gridImageId: string,
    data: GridData | null | undefined,
    imageId: string,
): { fovea: Position2D | null; discEdge: Position2D | null } {
    const source = enfaceSourceId(registration, gridImageId);
    const map = (p: Position2D | undefined) =>
        p
            ? (registration.mapPosition(source, imageId, {
                  x: p.x,
                  y: p.y,
                  index: 0,
              } as Position) ?? null)
            : null;
    return { fovea: map(data?.fovea), discEdge: map(data?.disc_edge) };
}

export class ETDRSGridItemOverlay implements Overlay {
    lineWidth = 1;
    strokeStyle = "rgba(255,255,255, 1)";
    name: string = "ETRDR grid item";

    constructor(
        private readonly source: ETDRSGridSource,
        private readonly registration: Registration,
        private readonly settings: { radiusFraction: number },
    ) {}

    /** Back-compat: FormAnnotation-like or etdrsGridType snapshot. */
    static fromAnnotationLike(
        annotation: etdrsGridType & { id?: number },
        registration: Registration,
        settings: { radiusFraction: number },
    ) {
        if (typeof annotation.id === "number") {
            return new ETDRSGridItemOverlay(
                { kind: "annotation", id: annotation.id },
                registration,
                settings,
            );
        }
        return new ETDRSGridItemOverlay(
            { kind: "snapshot", data: annotation },
            registration,
            settings,
        );
    }

    private resolveGrid(): etdrsGridType | undefined {
        if (this.source.kind === "snapshot") {
            return this.source.data;
        }
        const annotation = formAnnotations.get(this.source.id);
        if (!annotation?.form_data) return undefined;
        return {
            image_id: String(annotation.image_id ?? ""),
            form_data: annotation.form_data as etdrsGridType["form_data"],
        };
    }

    repaint(viewerContext: ViewerContext) {
        const resolved = this.resolveGrid();
        if (!resolved) return;
        const { fovea, discEdge } = gridPointsIn(
            this.registration,
            String(resolved.image_id),
            resolved.form_data,
            viewerContext.image.image_id,
        );
        if (!fovea || !discEdge) return;
        this.paint(viewerContext.context2D, viewerContext, fovea, discEdge);
        if (this.source.kind === "snapshot")
            this.paintAiPoints(viewerContext.context2D, viewerContext, [
                fovea,
                discEdge,
            ]);
    }

    private paint(
        ctx: CanvasRenderingContext2D,
        viewerContext: ViewerContext,
        fovea: Position2D,
        diskBorder: Position2D,
    ) {
        ctx.lineWidth = this.lineWidth;
        ctx.strokeStyle = this.strokeStyle;
        ctx.fillStyle = this.strokeStyle;
        ctx.font = "14px Arial";
        ctx.imageSmoothingEnabled = true;

        const p_fovea = viewerContext.imageToViewerCoordinates(fovea);
        const p_diskBorder = viewerContext.imageToViewerCoordinates(diskBorder);

        const dx = p_diskBorder.x - p_fovea.x;
        const dy = p_diskBorder.y - p_fovea.y;
        const pix_per_mm =
            (1 / 3) *
            this.settings.radiusFraction *
            Math.sqrt(dx * dx + dy * dy);

        // One path, so a casing never covers a line drawn before it.
        ctx.beginPath();
        for (const diameter of [1, 3, 6]) {
            const r = (diameter / 2) * pix_per_mm;
            ctx.moveTo(p_fovea.x + r, p_fovea.y);
            ctx.ellipse(p_fovea.x, p_fovea.y, r, r, 0, 0, 2 * Math.PI);
        }
        const r = 0.5 * Math.sqrt(2) * pix_per_mm;
        for (const sdx of [-1, 1]) {
            for (const sdy of [-1, 1]) {
                ctx.moveTo(
                    p_fovea.x + 0.5 * sdx * r,
                    p_fovea.y + 0.5 * sdy * r,
                );
                ctx.lineTo(p_fovea.x + 3 * sdx * r, p_fovea.y + 3 * sdy * r);
            }
        }
        cased(ctx, () => ctx.stroke());

        // Draw additionalCircles legend with labels (bottom-left), if size allows
        const r_max = 0.5 * ETDRS_CIRCLES.O2 * pix_per_mm;
        const y = viewerContext.viewerSize.height - 10 - r_max;
        let x = 10;
        if (r_max < 0.1 * viewerContext.viewerSize.height) {
            for (const [name, diameter] of Object.entries(ETDRS_CIRCLES)) {
                ctx.lineWidth = this.lineWidth;
                ctx.strokeStyle = this.strokeStyle;
                const r = diameter / 2;
                x += r * pix_per_mm;
                ctx.beginPath();
                ctx.ellipse(
                    x,
                    y,
                    r * pix_per_mm,
                    r * pix_per_mm,
                    0,
                    0,
                    2 * Math.PI,
                );
                cased(ctx, () => ctx.stroke());
                casedText(ctx, name, x, y - r_max - 5);
                x += Math.max(r * pix_per_mm, 20);
                x += 10;
            }
        }
    }

    /** The model's fovea and disc edge: dashed rings labelled "AI". */
    private paintAiPoints(
        ctx: CanvasRenderingContext2D,
        viewerContext: ViewerContext,
        points: Position2D[],
    ) {
        ctx.strokeStyle = AI_COLOUR;
        ctx.fillStyle = AI_COLOUR;
        ctx.lineWidth = 2;
        ctx.font = "12px 'IBM Plex Sans', sans-serif";
        ctx.textAlign = "start";
        for (const point of points) {
            const p = viewerContext.imageToViewerCoordinates(point);
            ctx.beginPath();
            ctx.arc(p.x, p.y, 6, 0, 2 * Math.PI);
            ctx.setLineDash([3, 2]);
            cased(ctx, () => ctx.stroke(), AI_CASING);
            ctx.setLineDash([]);
            casedText(ctx, "AI", p.x + 8, p.y - 5, AI_CASING);
        }
    }
}
