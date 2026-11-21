<!--
@component
The Selected pane for a distance line: its length and two points. Lines are not saved, so there is no save status.
-->
<script lang="ts">
    import * as StructuredList from "$lib/components/ui/structured-list/index.js";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, type Snippet } from "svelte";
    import {
        lengthText,
        type DistanceLines,
        type Line,
    } from "../distanceLines.svelte";
    import type { Scale } from "../imageScale";
    import PaneHeader from "./PaneHeader.svelte";

    let {
        id,
        line,
        lines,
        scale,
        remove,
    }: {
        id: string;
        line: Line;
        lines: DistanceLines;
        scale: Scale | null;
        remove?: Snippet;
    } = $props();
    const viewerContext = getContext<ViewerContext>("viewerContext");
    // Numbered among this image's or B-scan's lines, as the rows are.
    const n = $derived(
        lines.lines
            .filter((l) => l.index === viewerContext.index)
            .indexOf(line) + 1,
    );
    const point = (p: { x: number; y: number }) =>
        `(${p.x.toFixed(0)}, ${p.y.toFixed(0)})`;
    const rows = $derived([
        ["Length", lengthText(line, scale)],
        ["Points", `${point(line.start)} – ${point(line.end)}`],
    ]);
</script>

<PaneHeader {id} name="Line {n}" type="Distance line" {remove} />
<div class="min-h-0 flex-1 overflow-y-auto py-2">
    <StructuredList.Root condensed>
        <StructuredList.Body>
            {#each rows as [label, value] (label)}
                <StructuredList.Row>
                    <StructuredList.Cell>{label}</StructuredList.Cell>
                    <StructuredList.Cell class="tabular-nums"
                        >{value}</StructuredList.Cell
                    >
                </StructuredList.Row>
            {/each}
        </StructuredList.Body>
    </StructuredList.Root>
</div>
