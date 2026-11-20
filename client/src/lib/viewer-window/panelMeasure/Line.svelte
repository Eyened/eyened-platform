<!--
@component
One distance line in Layers: "Line n · length", its two points, and Delete. The current line is marked; hover or focus inside the row highlights the line.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
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

<div
    class="flex items-start gap-1 border-s-3 py-1 ps-7 pe-2 focus-within:bg-layer-hover-01 hover:bg-layer-hover-01 {current
        ? 'border-border-interactive bg-layer-selected-01'
        : 'border-transparent'}"
    role="group"
    aria-label="Line {n}"
    aria-current={current ? "true" : undefined}
    onpointerenter={() => onhighlight(true)}
    onpointerleave={() => onhighlight(false)}
    onfocusin={() => onhighlight(true)}
    onfocusout={() => onhighlight(false)}
>
    <div class="min-w-0 flex-1 px-1">
        <p class="text-body-compact-01 text-text-primary tabular-nums">
            Line {n} · {length}
        </p>
        <p class="text-helper-text-01 text-text-secondary tabular-nums">
            {point(line.start)} – {point(line.end)}
        </p>
    </div>
    <IconButton
        size="icon-xs"
        label="Delete line {n}"
        data-delete-line
        onclick={ondelete}
    >
        <TrashCan />
    </IconButton>
</div>
