<!--
@component
Layers › Distance lines for the selected viewport: today's Measure tool, armed while this section is open and on screen, its Image resolution block, and one row per line on this image or B-scan.
-->
<script lang="ts">
    import type { Line, MeasureTool } from "$lib/viewer/tools/Measure.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import LineRow from "$lib/viewer-window/panelMeasure/Line.svelte";
    import { getContext, tick } from "svelte";
    import type { GridLayers } from "./gridLayers.svelte";
    import ImageResolution from "./ImageResolution.svelte";
    import LayerSection from "./LayerSection.svelte";

    let {
        measure,
        grids,
        open,
        ontoggle,
        shown,
    }: {
        measure: MeasureTool;
        grids: GridLayers;
        open: boolean;
        ontoggle: () => void;
        /** True while Layers is on screen. */
        shown: boolean;
    } = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    let section: HTMLElement | undefined = $state();
    const lines = $derived(
        [...measure.lines].filter((line) => line.index === viewerContext.index),
    );

    // The Measure tool draws and paints its lines only while this section is open and on screen; the lines stay for next time.
    $effect(() => {
        if (!shown || !open) return;
        return viewerContext.addOverlay(measure);
    });

    // The pressed Delete goes with its row, so focus moves to the next line's Delete, else the previous one, else the header.
    async function remove(line: Line, i: number) {
        measure.highlight(undefined);
        measure.lines.delete(line);
        await tick();
        const deletes =
            section?.querySelectorAll<HTMLElement>("[data-delete-line]") ?? [];
        (
            deletes[i] ??
            deletes[i - 1] ??
            section?.querySelector<HTMLElement>("button")
        )?.focus();
    }
</script>

<div bind:this={section}>
    <LayerSection title="Distance lines" count={lines.length} {open} {ontoggle}>
        <ImageResolution {measure} {grids} />
        <ul>
            {#each lines as line, i (line)}
                <li>
                    <LineRow
                        {line}
                        n={i + 1}
                        {measure}
                        ondelete={() => remove(line, i)}
                    />
                </li>
            {/each}
        </ul>
    </LayerSection>
</div>
