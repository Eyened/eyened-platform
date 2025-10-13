<script lang="ts">
    import type { MeasureTool } from "$lib/viewer/tools/Measure.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { BinaryMask, ProbabilityMask } from "$lib/webgl/mask.svelte";
    import { getContext } from "svelte";
    import type { SegmentationGET } from "../../../types/openapi_types";
    export interface Props {
        segmentation: SegmentationGET;
        measureTool: MeasureTool;
    }
    let { segmentation, measureTool }: Props = $props();
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
    const { segmentationContext } = mainViewerContext;

    let area = $derived.by(() => {
        const segmentationItem = segmentationContext.getSegmentationItem(segmentation);
        const mask = segmentationItem?.getMask(viewerContext.index);
        if (mask instanceof BinaryMask || mask instanceof ProbabilityMask) {
            if (mask.pixelArea == undefined) return undefined;
            const areamm2 =
                (mask.pixelArea *
                    measureTool.imageResX *
                    measureTool.imageResY) /
                1e6;
            return areamm2;
        }
        return 0;
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
