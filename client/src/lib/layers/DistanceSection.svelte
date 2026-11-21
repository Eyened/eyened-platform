<!--
@component
Layers › Distance lines for the selected viewport: one row per line on this image or B-scan, the selected line marked.
-->
<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import LineRow from "$lib/viewer-window/panelMeasure/Line.svelte";
    import { getContext } from "svelte";
    import {
        lengthText,
        type DistanceLines,
        type Line,
    } from "./distanceLines.svelte";
    import type { Scale } from "./imageScale";
    import LayerSection from "./LayerSection.svelte";
    import { focusAfterDelete } from "./focusAfterDelete";

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
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    let section: HTMLElement | undefined = $state();
    const lines = $derived(
        distance.lines.filter((line) => line.index === viewerContext.index),
    );

    function remove(line: Line, event: MouseEvent) {
        const focus = focusAfterDelete(
            (event.currentTarget as Element).closest("[data-layer-row]"),
            section ?? null,
        );
        distance.remove(line);
        focus();
    }
</script>

<div bind:this={section} data-layer-section="distance">
    <LayerSection
        title="Distance lines"
        count={lines.length}
        {open}
        {ontoggle}
        empty="Use the Distance tool to draw one."
    >
        <ul>
            {#each lines as line, i (line)}
                <li>
                    <LineRow
                        {line}
                        n={i + 1}
                        length={lengthText(line, scale)}
                        current={mainViewerContext.selection.line() === line}
                        onselect={() =>
                            mainViewerContext.selection.select(
                                mainViewerContext.selection.line() === line
                                    ? null
                                    : { kind: "line", line, lines: distance },
                            )}
                        onhighlight={(on) =>
                            (distance.highlighted = on ? line : undefined)}
                        ondelete={(e) => remove(line, e)}
                    />
                </li>
            {/each}
        </ul>
    </LayerSection>
</div>
