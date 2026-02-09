import type { Registration } from "$lib/registration/registration";
import type { Position, Position2D } from "$lib/types";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

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
}
export class ETDRSGridItemOverlay implements Overlay {
    lineWidth = 1;
    strokeStyle = 'rgba(255,255,255, 1)';
    name: string = 'ETRDR grid item';
    cursorCircle: string | undefined = undefined;

    constructor(
        private readonly annotation: etdrsGridType,
        private readonly registration: Registration,
        private readonly settings: { radiusFraction: number }

    ) { }

    keydown(keyEvent: ViewerEvent<KeyboardEvent>) {
        const { event } = keyEvent;
        const circles: Record<string, string[]> = {
            C: ['C0', 'C1', 'C2'],
            I: ['I1', 'I2'],
            O: ['O1', 'O2'],
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

        const f = this.annotation.form_data?.fovea;
        const d = this.annotation.form_data?.disc_edge;
        const srcId = String(this.annotation.image_id);

        if (!f || !d) return;

        const fovea = this.registration.mapPosition(
            srcId,
            image.image_id,
            { ...f, index: 0 } as Position
        );
        const discEdge = this.registration.mapPosition(
            srcId,
            image.image_id,
            { ...d, index: 0 } as Position
        );
        if (!fovea || !discEdge) return;

        this.paint(context2D, viewerContext, fovea, discEdge);
    }

    private paint(ctx: CanvasRenderingContext2D, viewerContext: ViewerContext, fovea: Position2D, diskBorder: Position2D) {
        ctx.lineWidth = this.lineWidth;
        ctx.strokeStyle = this.strokeStyle;
        ctx.fillStyle = this.strokeStyle;
        ctx.font = '14px Arial';
        ctx.imageSmoothingEnabled = true;

        const p_fovea = viewerContext.imageToViewerCoordinates(fovea);
        const p_diskBorder = viewerContext.imageToViewerCoordinates(diskBorder);

        const dx = p_diskBorder.x - p_fovea.x;
        const dy = p_diskBorder.y - p_fovea.y;
        const pix_per_mm = (1 / 3) * this.settings.radiusFraction * Math.sqrt(dx * dx + dy * dy);

        for (const diameter of [C, I, O]) {
            const r = diameter / 2;
            ctx.beginPath();
            ctx.ellipse(p_fovea.x, p_fovea.y, r * pix_per_mm, r * pix_per_mm, 0, 0, 2 * Math.PI);
            ctx.stroke();
        }

        const r = 0.5 * Math.sqrt(2) * pix_per_mm;
        for (const sdx of [-1, 1]) {
            for (const sdy of [-1, 1]) {
                ctx.moveTo(p_fovea.x + 0.5 * sdx * r, p_fovea.y + 0.5 * sdy * r);
                ctx.lineTo(p_fovea.x + 3 * sdx * r, p_fovea.y + 3 * sdy * r);
                ctx.stroke();
            }
        }

        // Draw additionalCircles legend with labels (bottom-left), if size allows
        const r_max = 0.5 * additionalCircles['O2'] * pix_per_mm;
        let y = viewerContext.viewerSize.height - 10 - r_max;
        let x = 10;
        if (r_max < 0.1 * viewerContext.viewerSize.height) {
            for (const [name, diameter] of Object.entries(additionalCircles)) {
                const selected = name === this.cursorCircle;
                if (selected) {
                    ctx.lineWidth = 4 * this.lineWidth;
                    ctx.strokeStyle = 'rgba(100, 255, 100, 1)';
                } else {
                    ctx.lineWidth = this.lineWidth;
                    ctx.strokeStyle = this.strokeStyle;
                }
                const r = diameter / 2;
                x += r * pix_per_mm;
                ctx.beginPath();
                ctx.ellipse(x, y, r * pix_per_mm, r * pix_per_mm, 0, 0, 2 * Math.PI);
                ctx.stroke();
                ctx.fillText(name, x, y - r_max - 5);
                x += Math.max(r * pix_per_mm, 20);
                x += 10;
            }
        }

        // Draw cursor-following circle if active
        const cursor = this.registration.getPosition(viewerContext.image.image_id);
        if (cursor && this.cursorCircle) {
            ctx.lineWidth = this.lineWidth;
            ctx.strokeStyle = this.strokeStyle;
            const diameter = additionalCircles[this.cursorCircle];
            const r_c = diameter / 2;
            const { x: cx, y: cy } = viewerContext.imageToViewerCoordinates(cursor);
            ctx.beginPath();
            ctx.ellipse(cx, cy, r_c * pix_per_mm, r_c * pix_per_mm, 0, 0, 2 * Math.PI);
            ctx.stroke();
            viewerContext.cursorStyle = 'none';
        } else {
            viewerContext.cursorStyle = 'default';
        }
    }
}


