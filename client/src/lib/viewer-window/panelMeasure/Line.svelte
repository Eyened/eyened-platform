<!--
@component
One distance line in Layers: "Line n · length" and its two points, with Delete at the right. The current line is marked; hover or focus inside the row highlights the line.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import LayerRow from "$lib/layers/LayerRow.svelte";
    import type { Line } from "$lib/layers/distanceLines.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";

    let {
        line,
        n,
        length,
        current,
        onhighlight,
        ondelete,
    }: {
        line: Line;
        /** The line's number among this image's or B-scan's lines, in drawing order. */
        n: number;
        length: string;
        current: boolean;
        onhighlight: (on: boolean) => void;
        ondelete: () => void;
    } = $props();

    const point = (p: { x: number; y: number }) =>
        `(${p.x.toFixed(0)}, ${p.y.toFixed(0)})`;
</script>

<LayerRow
    label="Line {n}"
    name="Line {n} · {length}"
    selected={current}
    aria-current={current ? "true" : undefined}
    onpointerenter={() => onhighlight(true)}
    onpointerleave={() => onhighlight(false)}
    onfocusin={() => onhighlight(true)}
    onfocusout={() => onhighlight(false)}
>
    {#snippet icons()}
        <IconButton
            size="icon-xs"
            label="Delete line {n}"
            data-delete-line
            onclick={ondelete}
        >
            <TrashCan />
        </IconButton>
    {/snippet}
    <p
        class="ps-8 pe-2 pb-1 text-helper-text-01 text-text-secondary tabular-nums"
    >
        {point(line.start)} – {point(line.end)}
    </p>
</LayerRow>
