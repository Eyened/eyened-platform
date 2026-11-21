<!--
@component
The Selected pane for a distance line: its length and two points. Lines are not saved, so there is no save status.
-->
<script lang="ts">
    import type { Snippet } from "svelte";
    import {
        lengthText,
        type DistanceLines,
        type Line,
    } from "../distanceLines.svelte";
    import type { Scale } from "../imageScale";
    import PaneFields from "./PaneFields.svelte";
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
    // Numbered among its own image's or B-scan's lines, as the rows are.
    const n = $derived(
        lines.lines.filter((l) => l.index === line.index).indexOf(line) + 1,
    );
    const point = (p: { x: number; y: number }) =>
        `(${p.x.toFixed(0)}, ${p.y.toFixed(0)})`;
    const rows = $derived<[string, string][]>([
        ["Length", lengthText(line, scale)],
        ["Points", `${point(line.start)} – ${point(line.end)}`],
    ]);
</script>

<PaneHeader {id} name="Line {n}" type="Distance line" {remove} />
<div class="min-h-0 flex-1 overflow-y-auto py-2">
    <PaneFields {rows} />
</div>
