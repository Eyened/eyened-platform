<script lang="ts">
    import type { MeasureTool } from "$lib/viewer/tools/Measure.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { BinaryMask, ProbabilityMask } from "$lib/webgl/mask.svelte";
    import { getContext } from "svelte";
    import type { Segmentation } from "../panelSegmentation/segmentationContext.svelte";
    export interface Props {
        segmentation: Segmentation;
        measureTool: MeasureTool;
    }
    let { segmentation, measureTool }: Props = $props();
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
    const { segmentationContext } = mainViewerContext;

    let area = $state<number | undefined>(undefined);

    $effect(() => {
        const index = viewerContext.index;
        const resX = measureTool.imageResX;
        const resY = measureTool.imageResY;

        const segmentationItem = segmentationContext.getSegmentationItem(segmentation);
        const mask = segmentationItem.getMask(index);
        if (!mask) {
            area = undefined;
            return;
        }

        if (mask instanceof BinaryMask) {
            const pixelArea = mask.pixelArea;
            area = (pixelArea * resX * resY) / 1e6;
            return;
        }

        if (mask instanceof ProbabilityMask) {
            // pixelArea tracks data changes; threshold is applied at read time
            mask.pixelArea;
            const pixelArea = mask.computePixelArea(segmentationItem.threshold);
            area = (pixelArea * resX * resY) / 1e6;
            return;
        }

        area = 0;
    });
</script>

<div class="segmentation-info">
    <div class="header">
        <span class="segmentation-id">[{segmentation.id}]</span>
        <span class="feature-name">{segmentation.feature.name}</span>
    </div>
    <span class="area">
        {#if area !== undefined}
            {#if area < 0.01}
                {(area * 1e6).toFixed(0)} μm²
            {:else}
                {area.toFixed(4)} mm²
            {/if}
        {/if}
    </span>
</div>

<style>
    div {
        display: flex;
    }
    div.header {
        flex-direction: row;
        gap: 0.5em;
        align-items: center;
    }
    div.segmentation-info {
        flex-direction: column;
        background-color: rgba(255, 255, 255, 0.1);
        margin: 0.1em;
        border-radius: 0.2em;
    }
    div.segmentation-info:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }
    span.segmentation-id {
        font-size: x-small;
    }
    span {
        font-size: small;
        opacity: 0.8;
    }
    .area {
        flex: 1;
        align-items: right;
    }
</style>
