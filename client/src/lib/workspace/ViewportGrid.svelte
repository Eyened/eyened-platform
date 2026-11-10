<!--
@component
The viewport grid for the current preset and track sizes, its splitters, and its maximise mode:
the same frame nodes restyled into one big viewport under a live strip, so no viewer is rebuilt.
While the thumbnail strip is on, maximise hides the other viewports instead.
-->
<script lang="ts">
    import { getContext, setContext, type Snippet } from "svelte";
    import type { ViewportTitle } from "./imageMeta";
    import Splitter from "./Splitter.svelte";
    import ViewportFrame from "./ViewportFrame.svelte";
    import type { Workspace } from "./workspace.svelte";
    import {
        GRID_GAP,
        setSplit,
        splitRange,
        splitterSegments,
        type Axis,
        type SplitterSegment,
    } from "./workspaceRules";

    let {
        viewer,
        titleFor,
        onchooseimage,
    }: {
        viewer: Snippet<[string]>;
        titleFor: (imageId: string) => ViewportTitle | null;
        onchooseimage: () => void;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const uid = $props.id();
    const STRIP_TILE_WIDTH = 132;
    const STRIP_TILE_HEIGHT = 92;
    const STRIP_HEIGHT = 104;
    const STRIP_STEP = STRIP_TILE_WIDTH + GRID_GAP;

    let grid: HTMLDivElement | undefined = $state();
    let scroller: HTMLDivElement | undefined = $state();
    let width = $state(0);
    let height = $state(0);
    let stripX = $state(0);
    let dragStart: number[] | null = null;

    // Viewer.svelte clips its WebGL drawing to this box, so a strip tile scrolled out of view draws nothing.
    setContext("viewportClip", () => grid?.getBoundingClientRect() ?? null);

    const preset = $derived(workspace.preset);
    const maximised = $derived(workspace.maximised);
    const segments = $derived(splitterSegments(preset));

    const sum = (sizes: readonly number[], from = 0, to = sizes.length) =>
        sizes.slice(from, to).reduce((a, b) => a + b, 0);
    const frs = (sizes: readonly number[]) =>
        sizes.map((s) => `${s}fr`).join(" ");
    const template = $derived(
        `gap: ${GRID_GAP}px; grid-template-columns: ${frs(workspace.colSizes)}; grid-template-rows: ${frs(workspace.rowSizes)};`,
    );

    function modeOf(position: number): "grid" | "big" | "tile" | "hidden" {
        if (maximised === null) return "grid";
        if (position === maximised) return "big";
        return workspace.strip ? "hidden" : "tile";
    }

    function cellStyle(position: number): string {
        if (maximised === null) {
            const c = preset.cells[position];
            return `grid-column: ${c.col + 1} / span ${c.colSpan}; grid-row: ${c.row + 1};`;
        }
        // The thumbnail strip stands in for the maximise strip; hidden viewports keep their views.
        if (workspace.strip)
            return position === maximised
                ? "position: absolute; inset: 0;"
                : "display: none;";
        if (position === maximised)
            return `position: absolute; inset: ${STRIP_HEIGHT}px 0 0 0;`;
        const tile = position < maximised ? position : position - 1;
        return `position: absolute; top: 0; width: ${STRIP_TILE_WIDTH}px; height: ${STRIP_TILE_HEIGHT}px; left: ${tile * STRIP_STEP - stripX}px;`;
    }

    /** The middle of the gap before track `line`, across the axis. */
    function lineAt(sizes: readonly number[], line: number): string {
        const gaps = GRID_GAP * (sizes.length - 1);
        return `calc((100% - ${gaps}px) * ${sum(sizes, 0, line) / sum(sizes)} + ${GRID_GAP * line - GRID_GAP / 2}px)`;
    }

    /** Start and length of tracks [from, to), along the axis. */
    function extent(
        sizes: readonly number[],
        from: number,
        to: number,
    ): [string, string] {
        const unit = `(100% - ${GRID_GAP * (sizes.length - 1)}px) / ${sum(sizes)}`;
        return [
            `calc(${unit} * ${sum(sizes, 0, from)} + ${GRID_GAP * from}px)`,
            `calc(${unit} * ${sum(sizes, from, to)} + ${GRID_GAP * (to - from - 1)}px)`,
        ];
    }

    const sizesOf = (axis: Axis) =>
        axis === "col" ? workspace.colSizes : workspace.rowSizes;
    const lengthOf = (axis: Axis) => (axis === "col" ? width : height);
    const rangeOf = (
        seg: SplitterSegment,
        sizes: readonly number[] = sizesOf(seg.axis),
    ) => splitRange(preset, sizes, seg.axis, seg.line, lengthOf(seg.axis));

    function moveTo(seg: SplitterSegment, sizes: readonly number[], a: number) {
        const r = rangeOf(seg, sizes);
        const target = Number.isNaN(a) ? sizes[seg.line - 1] : a;
        workspace.setTracks(
            seg.axis,
            setSplit(sizes, seg.line, Math.min(r.hi, Math.max(r.lo, target))),
        );
    }

    function splitterStyle(seg: SplitterSegment): string {
        const across = sizesOf(seg.axis);
        const [start, length] = extent(
            seg.axis === "col" ? workspace.rowSizes : workspace.colSizes,
            seg.from,
            seg.to,
        );
        return seg.axis === "col"
            ? `left: calc(${lineAt(across, seg.line)} - 4px); top: ${start}; height: ${length};`
            : `top: calc(${lineAt(across, seg.line)} - 4px); left: ${start}; width: ${length};`;
    }

    function valuesOf(seg: SplitterSegment) {
        const r = rangeOf(seg);
        const pct = (v: number) => Math.round((v / r.total) * 100);
        return {
            now: pct(sizesOf(seg.axis)[seg.line - 1]),
            min: pct(r.lo),
            max: pct(r.hi),
        };
    }

    function controlsOf(seg: SplitterSegment): string {
        return preset.cells
            .flatMap((c, i) => {
                const [s, e] =
                    seg.axis === "col"
                        ? [c.col, c.col + c.colSpan]
                        : [c.row, c.row + 1];
                const [os, oe] =
                    seg.axis === "col"
                        ? [c.row, c.row + 1]
                        : [c.col, c.col + c.colSpan];
                const touches =
                    (s <= seg.line - 1 && seg.line - 1 < e) ||
                    (s <= seg.line && seg.line < e);
                return touches && os < seg.to && seg.from < oe
                    ? [`${uid}-slot-${i}`]
                    : [];
            })
            .join(" ");
    }

    const labelOf = (seg: SplitterSegment) =>
        `Resize ${seg.axis === "col" ? "columns" : "rows"} ${seg.line} and ${seg.line + 1}`;

    function resetPair(seg: SplitterSegment) {
        const initial = seg.axis === "col" ? preset.cols : preset.rows;
        const sizes = [...sizesOf(seg.axis)];
        sizes[seg.line - 1] = initial[seg.line - 1];
        sizes[seg.line] = initial[seg.line];
        workspace.setTracks(seg.axis, sizes);
    }

    // Keyboard focus on a strip tile scrolls it into view (WCAG 2.4.11).
    $effect(() => {
        const m = workspace.maximised;
        const s = workspace.selected;
        if (m === null || s === m || !scroller || workspace.strip) return;
        const left = (s < m ? s : s - 1) * STRIP_STEP;
        if (left < scroller.scrollLeft) scroller.scrollLeft = left;
        else if (left + STRIP_TILE_WIDTH > scroller.scrollLeft + width)
            scroller.scrollLeft = left + STRIP_TILE_WIDTH - width;
    });
</script>

<div
    bind:this={grid}
    bind:clientWidth={width}
    bind:clientHeight={height}
    class="grid"
    class:maximised={maximised !== null}
    style={maximised === null ? template : ""}
>
    {#each workspace.slots as slot, position (slot.id)}
        <ViewportFrame
            id="{uid}-slot-{position}"
            {position}
            {slot}
            title={slot.imageId ? titleFor(slot.imageId) : null}
            mode={modeOf(position)}
            style={cellStyle(position)}
            {viewer}
            {onchooseimage}
        />
    {/each}
    {#if maximised === null}
        {#each segments as seg (`${seg.axis}${seg.line}:${seg.from}`)}
            {@const value = valuesOf(seg)}
            <Splitter
                axis={seg.axis}
                label={labelOf(seg)}
                controls={controlsOf(seg)}
                valueNow={value.now}
                valueMin={value.min}
                valueMax={value.max}
                style={splitterStyle(seg)}
                ondragstart={() => (dragStart = [...sizesOf(seg.axis)])}
                ondrag={(d) => {
                    if (dragStart)
                        moveTo(
                            seg,
                            dragStart,
                            dragStart[seg.line - 1] +
                                d / rangeOf(seg, dragStart).perFr,
                        );
                }}
                ondragend={() => (dragStart = null)}
                oncancel={() => {
                    if (dragStart) workspace.setTracks(seg.axis, dragStart);
                    dragStart = null;
                }}
                onstep={(direction) => {
                    const sizes = sizesOf(seg.axis);
                    moveTo(
                        seg,
                        sizes,
                        sizes[seg.line - 1] +
                            (direction * lengthOf(seg.axis)) /
                                40 /
                                rangeOf(seg).perFr,
                    );
                }}
                onlimit={(end) =>
                    moveTo(
                        seg,
                        sizesOf(seg.axis),
                        end === "min" ? -Infinity : Infinity,
                    )}
                onreset={() => resetPair(seg)}
            />
        {/each}
    {:else if !workspace.strip}
        <div
            bind:this={scroller}
            class="strip-scroll"
            style="top: {STRIP_TILE_HEIGHT}px; height: {STRIP_HEIGHT -
                STRIP_TILE_HEIGHT}px;"
            onscroll={() => (stripX = scroller?.scrollLeft ?? 0)}
        >
            <div
                style="width: {(workspace.slots.length - 1) *
                    STRIP_STEP}px; height: 1px;"
            ></div>
        </div>
    {/if}
</div>
<div class="sr-only" aria-live="polite">{workspace.announcement}</div>

<style>
    .grid {
        position: relative;
        display: grid;
        flex: 1;
        min-width: 0;
        min-height: 0;
    }
    .grid.maximised {
        display: block;
        overflow: hidden;
    }
    .strip-scroll {
        position: absolute;
        left: 0;
        right: 0;
        overflow-x: auto;
        overflow-y: hidden;
    }
</style>
