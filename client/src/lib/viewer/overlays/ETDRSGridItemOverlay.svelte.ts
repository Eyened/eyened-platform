import { formAnnotations } from "$lib/data";
import type { Registration } from "$lib/registration/registration.svelte";
import type { Position, Position2D } from "$lib/types";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import { CursorPriority, type ViewerContext } from "../viewerContext.svelte";
import { cased, casedText } from "./casing";

// Carbon magenta 40, over a darker casing: on a bright fundus the default casing leaves it under 3:1.
const AI_COLOUR = "#ff7eb6";
const AI_CASING = "rgba(0, 0, 0, 0.8)";

/** The interim f / d placing's cross, until the Place ETDRS tool comes. */
export const ETDRS_LANDMARK_COLOUR = "rgba(0, 255, 0, 1)";

const [C, I, O] = [1, 3, 6];
const additionalCircles: Record<string, number> = {
    C0: C / 16,
    C1: C / 8,
    C2: C / 4,
    I1: I / 8,
    I2: I / 4,
    O1: O / 8,
    O2: O / 4,
};
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

export class ETDRSGridItemOverlay implements Overlay {
    lineWidth = 1;
    strokeStyle = "rgba(255,255,255, 1)";
    name: string = "ETRDR grid item";
    cursorCircle: string | undefined = undefined;

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

    keydown(keyEvent: ViewerEvent<KeyboardEvent>) {
        const { event } = keyEvent;
        const circles: Record<string, string[]> = {
            C: ["C0", "C1", "C2"],
            I: ["I1", "I2"],
            O: ["O1", "O2"],
        };
        const cycle = circles[event.key.toUpperCase()];
        if (cycle !== undefined) {
            const i = this.cursorCircle ? cycle.indexOf(this.cursorCircle) : 0;
            this.cursorCircle = cycle[(i + 1) % cycle.length];
        } else {
            this.cursorCircle = undefined;
        }
    }

    repaint(viewerContext: ViewerContext) {
        const { image, context2D } = viewerContext;
        const resolved = this.resolveGrid();
        if (!resolved) return;

        const f = resolved.form_data?.fovea;
        const d = resolved.form_data?.disc_edge;
        if (!f || !d) return;

        const srcId = this.enfaceSourceId(String(resolved.image_id));
        const fovea = this.registration.mapPosition(srcId, image.image_id, {
            x: f.x,
            y: f.y,
            index: 0,
        } as Position);
        const discEdge = this.registration.mapPosition(srcId, image.image_id, {
            x: d.x,
            y: d.y,
            index: 0,
        } as Position);
        if (!fovea || !discEdge) return;

        this.paint(context2D, viewerContext, fovea, discEdge);
        if (this.source.kind === "snapshot")
            this.paintAiPoints(context2D, viewerContext, [fovea, discEdge]);
    }

    /**
     * ETDRS landmarks are always enface 2D `(x, y)`.
     * For OCT volumes the enface plane is `${id}_proj` — use that node so we
     * never go through OCTToProj (which remaps `index → y` and drops enface y).
     * Plain CF PublicIDs have no proj edge and stay as-is (do *not* append `_proj`).
     */
    private enfaceSourceId(annotationImageId: string): string {
        if (annotationImageId.endsWith("_proj")) return annotationImageId;
        const projId = `${annotationImageId}_proj`;
        if (this.registration.getRegistrationItem(annotationImageId, projId)) {
            return projId;
        }
        return annotationImageId;
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
        for (const diameter of [C, I, O]) {
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
        const r_max = 0.5 * additionalCircles["O2"] * pix_per_mm;
        const y = viewerContext.viewerSize.height - 10 - r_max;
        let x = 10;
        if (r_max < 0.1 * viewerContext.viewerSize.height) {
            for (const [name, diameter] of Object.entries(additionalCircles)) {
                const selected = name === this.cursorCircle;
                if (selected) {
                    ctx.lineWidth = 4 * this.lineWidth;
                    ctx.strokeStyle = "rgba(100, 255, 100, 1)";
                } else {
                    ctx.lineWidth = this.lineWidth;
                    ctx.strokeStyle = this.strokeStyle;
                }
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

        // Draw cursor-following circle if active
        const cursor = this.registration.getPosition(
            viewerContext.image.image_id,
        );
        if (cursor && this.cursorCircle) {
            ctx.lineWidth = this.lineWidth;
            ctx.strokeStyle = this.strokeStyle;
            const diameter = additionalCircles[this.cursorCircle];
            const r_c = diameter / 2;
            const { x: cx, y: cy } =
                viewerContext.imageToViewerCoordinates(cursor);
            ctx.beginPath();
            ctx.ellipse(
                cx,
                cy,
                r_c * pix_per_mm,
                r_c * pix_per_mm,
                0,
                0,
                2 * Math.PI,
            );
            cased(ctx, () => ctx.stroke());
            viewerContext.claimCursor("none", CursorPriority.Hide);
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
