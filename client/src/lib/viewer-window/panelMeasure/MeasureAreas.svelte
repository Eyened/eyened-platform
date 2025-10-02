<script lang="ts">
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { MeasureTool } from "$lib/viewer/tools/Measure.svelte";
    import { getContext } from "svelte";
    import SegmentationArea from "./SegmentationArea.svelte";

    interface Props {
        measureTool: MeasureTool;
    }

    let { measureTool }: Props = $props();

    const { allSegmentations } = getContext<MainViewerContext>(
        "mainViewerContext",
    );
</script>

<ul>
    {#each allSegmentations as segmentation}
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
