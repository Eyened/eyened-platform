import type { ProbabilitySegmentation } from "$lib/webgl/probabilitySegmentation.svelte";
import type { ViewerContext } from "../viewerContext.svelte";
import type { DrawingExecutor } from "./segmentation";
import { BrushTool } from "./Brush";
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";

export class EnhanceTool extends BrushTool {

    private drawInterval: ReturnType<typeof setInterval> | undefined;
    public readonly hardness = $state(0.5); // higher hardness means sharper edge near brush border
    public readonly pressure = $state(0.25); // higher pressure means more effect
    public readonly enhance = $state(true); // enhance existing value, vs paint/erase to a fixed value


    constructor(
        drawingExecutor: DrawingExecutor,
        viewerContext: ViewerContext,
        segmentationContext: SegmentationContext,
        private readonly segmentation: ProbabilitySegmentation,
        private readonly segmentationItem: SegmentationItem
    ) {
        super(drawingExecutor, viewerContext, segmentationContext);
    }


    startDraw() {

        this.drawInterval = setInterval(() => {
            const index = this.viewerContext.index;
            if (this.lastPosition) {

                const settings = {
                    brushRadius: this.brushRadius,
                    hardness: this.hardness,
                    pressure: this.pressure,
                    enhance: this.enhance,
                    erase: this.mode === 'erase',
                    point: this.lastPosition
                };
                this.segmentation.drawEnhance(index, settings)
            }
        }, 1000 / 30); // 30 times per second

    }

    endDraw() {

        if (this.drawInterval) {
            clearInterval(this.drawInterval);
            this.drawInterval = undefined;
            const index = this.viewerContext.index;
            this.segmentation.endDraw(index);
            this.segmentationItem.checkpoint(index);
        }
    }

}