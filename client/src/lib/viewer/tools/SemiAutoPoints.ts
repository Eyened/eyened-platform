import type { Position2D } from "$lib/types";
import type { RenderTarget } from "$lib/webgl/types";
import type { ViewerEvent, Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

export type PromptPoint = Position2D;

interface SemiAutoPointToolOptions {
    getPositive: () => PromptPoint[];
    getNegative: () => PromptPoint[];
    setPoints: (positive: PromptPoint[], negative: PromptPoint[]) => void;
}

/**
 * Collects positive (left click) and negative (right click) prompts in image space.
 */
export class SemiAutoPointTool implements Overlay {
    constructor(private readonly options: SemiAutoPointToolOptions) {}

    pointerdown(e: ViewerEvent<PointerEvent>) {
        const { event, position, modifiers } = e;
        if (modifiers.alt || modifiers.shift || modifiers.ctrl || modifiers.meta) {
            return;
        }

        const p = { x: position.x, y: position.y };
        if (event.button === 0) {
            const positive = [...this.options.getPositive(), p];
            this.options.setPoints(positive, this.options.getNegative());
            return;
        }
        if (event.button === 2) {
            const negative = [...this.options.getNegative(), p];
            this.options.setPoints(this.options.getPositive(), negative);
        }
    }

    repaint(viewerContext: ViewerContext, _renderTarget: RenderTarget) {
        const ctx = viewerContext.context2D;
        const positive = this.options.getPositive();
        const negative = this.options.getNegative();

        const drawPoint = (pt: PromptPoint, color: string, label: string) => {
            const v = viewerContext.imageToViewerCoordinates(pt);
            const r = 6;
            ctx.save();
            ctx.beginPath();
            ctx.arc(v.x, v.y, r, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.globalAlpha = 0.9;
            ctx.fill();
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = "white";
            ctx.stroke();
            ctx.font = "11px Verdana, sans-serif";
            ctx.fillStyle = "white";
            ctx.globalAlpha = 1.0;
            ctx.fillText(label, v.x + 8, v.y - 8);
            ctx.restore();
        };

        for (const pt of positive) {
            drawPoint(pt, "#2ecc71", "+");
        }
        for (const pt of negative) {
            drawPoint(pt, "#e74c3c", "-");
        }

        if (positive.length > 0 || negative.length > 0) {
            viewerContext.cursorStyle = "crosshair";
        }
    }
}
