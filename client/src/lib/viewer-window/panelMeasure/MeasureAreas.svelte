<script lang="ts">
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { MeasureTool } from "$lib/viewer/tools/Measure.svelte";
    import { getSegmentationKey } from "../panelSegmentation/segmentationContext.svelte";
    import { getContext } from "svelte";
    import SegmentationArea from "./SegmentationArea.svelte";

    interface Props {
        measureTool: MeasureTool;
    }

    let { measureTool }: Props = $props();

    const { segmentationContext } = getContext<MainViewerContext>("mainViewerContext");

    const segmentations = $derived([
        ...segmentationContext.graderSegmentations,
        ...segmentationContext.modelSegmentations,
    ]);
</script>

<ul>
    {#each segmentations as segmentation (getSegmentationKey(segmentation))}
        <li>
            <SegmentationArea {segmentation} {measureTool} />
        </li>
    {/each}
</ul>

<style>
    ul {
        list-style-type: none;
        padding-left: 0.5em;
        padding-top: 0.5em;
        margin: 0;
    }
</style>
