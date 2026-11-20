<!--
@component
Layers › Distance lines for the selected viewport: one row per line on this image or B-scan, the current line marked.
-->
<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import LineRow from "$lib/viewer-window/panelMeasure/Line.svelte";
    import { getContext, tick } from "svelte";
    import {
        lengthText,
        type DistanceLines,
        type Line,
    } from "./distanceLines.svelte";
    import type { Scale } from "./imageScale";
    import LayerSection from "./LayerSection.svelte";

    let {
        distance,
        scale,
        open,
        ontoggle,
    }: {
        distance: DistanceLines;
        scale: Scale | null;
        open: boolean;
        ontoggle: () => void;
    } = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    let section: HTMLElement | undefined = $state();
    const lines = $derived(
        distance.lines.filter((line) => line.index === viewerContext.index),
    );

    // The pressed Delete goes with its row, so focus moves to the next line's Delete, else the previous one, else the header.
    async function remove(line: Line, i: number) {
        distance.remove(line);
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
        <ul>
            {#each lines as line, i (line)}
                <li>
                    <LineRow
                        {line}
                        n={i + 1}
                        length={lengthText(line, scale)}
                        current={distance.current === line}
                        onhighlight={(on) =>
                            (distance.highlighted = on ? line : undefined)}
                        ondelete={() => remove(line, i)}
                    />
                </li>
            {/each}
        </ul>
    </LayerSection>
</div>
