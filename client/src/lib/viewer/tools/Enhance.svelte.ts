import { ProbabilityMask } from "$lib/webgl/Mask";
import type { ViewerContext } from "../viewerContext.svelte";
import type { DrawingExecutor } from "./segmentation";
import { BrushTool } from "./Brush";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";

export class EnhanceTool extends BrushTool {

    private drawInterval: ReturnType<typeof setInterval> | undefined;
    public readonly hardness = $state(0.5); // higher hardness means sharper edge near brush border
    public readonly pressure = $state(0.25); // higher pressure means more effect
    public readonly enhance = $state(true); // enhance existing value, vs paint/erase to a fixed value


    constructor(
        drawingExecutor: DrawingExecutor,
        viewerContext: ViewerContext,
        segmentationContext: SegmentationContext
    ) {
        super(drawingExecutor, viewerContext, segmentationContext);
    }


    async startDraw() {
        const segmentationItem = this.segmentationContext.segmentationItem;
        if (!segmentationItem) {
            console.warn("No segmentation");
            return;
        }

        const segmentationState = segmentationItem.getSegmentationState(this.viewerContext.index, true)!;
        const mask = segmentationState.mask;
        if (!(mask instanceof ProbabilityMask)) {
            console.warn("No probability segmentation");
            return;
        }

        this.drawInterval = setInterval(() => {
            if (this.lastPosition) {
                const settings = {
                    brushRadius: this.brushRadius,
                    hardness: this.hardness,
                    pressure: this.pressure,
                    enhance: this.enhance,
                    erase: this.mode === 'erase',
                    point: this.lastPosition,
                    aspectRatio: this.viewerContext.aspectRatio
                };
                mask.drawEnhance(settings)
            }
        }, 1000 / 30); // 30 times per second

    }

    endDraw() {
        const segmentationItem = this.segmentationContext.segmentationItem;
        if (!segmentationItem) {
            console.warn("No segmentation item");
            return;
        }
        if (this.drawInterval) {
            clearInterval(this.drawInterval);
            this.drawInterval = undefined;
            const scanNr = this.viewerContext.index;
            segmentationItem.draw(scanNr, null, {});
        }
    }

}