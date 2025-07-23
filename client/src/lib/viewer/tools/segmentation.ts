import type { Position2D } from "$lib/types";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

const paintKey = 'Q';
const eraseKey = 'W';

export type DrawingMode = 'erase' | 'paint';

export interface DrawingExecutor {
    getCtx(): CanvasRenderingContext2D;
    draw(ctx: CanvasRenderingContext2D, mode: 'paint' | 'erase'): Promise<void>;
}


export abstract class SegmentationTool implements Overlay {

    paintColor = 'rgba(200, 255, 200, 0.5)';
    eraseColor = 'rgba(255, 200, 200, 0.5)';
    fillColor = 'rgba(255, 255, 255, 0.4)';


    drawingState: DrawingMode = 'paint';
    currentPoints: Position2D[] | undefined;
    lastPosition: Position2D | undefined;
    syncing: boolean = false;

    constructor(
        protected readonly drawingExecutor: DrawingExecutor,
        protected readonly viewerContext: ViewerContext,
        protected readonly segmentationContext: SegmentationContext,
    ) {
    }

    abstract executeDraw(ctx: CanvasRenderingContext2D, viewerContext: ViewerContext): void;

    get mode() {
        return ((this.drawingState === 'paint') !== this.flipDrawErase) ? 'paint' : 'erase';
    }
    get flipDrawErase(): boolean {
        return this.segmentationContext.flipDrawErase;
    }

    get drawingColor(): string {
        if (this.mode === 'paint') {
            return this.flipDrawErase ? this.eraseColor : this.paintColor;
        } else if (this.mode === 'erase') {
            return this.flipDrawErase ? this.paintColor : this.eraseColor;
        }
        throw new Error(`Invalid drawing mode: ${this.mode}`);
    }

    keydown(e: ViewerEvent<KeyboardEvent>) {
        const { event: { repeat, key }, viewerContext } = e;
        if (repeat) return;

        const k = key.toUpperCase();
        if (k == paintKey) this.drawingState = 'paint';
        if (k == eraseKey) this.drawingState = 'erase';

        if (k == paintKey || k == eraseKey) {
            this.startDraw(viewerContext);
        }
    }

    keyup(e: ViewerEvent<KeyboardEvent>) {
        const { event, viewerContext, } = e;
        const k = event.key.toUpperCase();
        if (k == paintKey || k == eraseKey) {
            this.endDraw(viewerContext);
        }
    }

    startDraw(viewerContext: ViewerContext) {
        this.currentPoints = [this.lastPosition!];
    }

    endDraw(viewerContext: ViewerContext) {
        if (this.currentPoints) {
            this.syncing = true;

            const ctx = this.drawingExecutor.getCtx();
            this.executeDraw(ctx, viewerContext);
            this.drawingExecutor.draw(ctx, this.mode).then(() => this.syncing = false);
            this.currentPoints = undefined;
        }
    }

    repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
        if (this.syncing) {
            viewerContext.cursorStyle = 'wait';            
        }
    }

}
