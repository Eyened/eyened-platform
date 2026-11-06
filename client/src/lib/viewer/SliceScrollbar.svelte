<!--
@component
A volume's right edge: the slice scrollbar with ticks on slices that have segmentation data, and the readout line.
Numbers are shown 1-based; the stored index stays 0-based.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import Locked from "carbon-icons-svelte/lib/Locked.svelte";
    import Unlocked from "carbon-icons-svelte/lib/Unlocked.svelte";
    import { getContext } from "svelte";
    import {
        BSCAN_LINKS_SHOW_ALL_MAX,
        buildBscanDisplayItems,
    } from "./bscanLinksDisplay";
    import type { MainViewerContext } from "./overlays/MainViewerContext.svelte";
    import { tickAt, tickPercent } from "./sliceTicks";
    import { readoutParts } from "./viewControlsFit";
    import type { ViewerContext } from "./viewerContext.svelte";

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const { depth } = viewerContext.image;
    const word =
        viewerContext.image.orientation === "axial" ? "B-scan" : "Slice";

    const scanIndices = $derived(
        mainViewerContext.segmentationContext.scan_indices,
    );
    // The pointer from another viewer can land between slices or past the ends.
    const index = $derived(
        Math.max(0, Math.min(depth - 1, Math.round(viewerContext.index))),
    );
    const numbers = $derived(buildBscanDisplayItems(scanIndices, index));
    const showCount = $derived(scanIndices.length > BSCAN_LINKS_SHOW_ALL_MAX);
    const countText = $derived(`${scanIndices.length} with data`);

    let track: HTMLElement | undefined = $state();
    let numbersWidth = $state(0);
    let countWidth = $state(0);
    let wordWidth = $state(0);
    let readoutWidth = $state(0);

    // Room for the line's Lock button, gaps and padding.
    const LINE_CHROME_PX = 64;
    const parts = $derived(
        readoutParts(
            {
                numbers: scanIndices.length > 0 ? numbersWidth : Infinity,
                count: showCount ? countWidth : 0,
                word: wordWidth,
                readout: readoutWidth,
            },
            viewerContext.viewerSize.width - LINE_CHROME_PX,
        ),
    );

    function onpointerdowncapture(e: PointerEvent) {
        if (e.button !== 0 || !track) return;
        const box = track.getBoundingClientRect();
        const hit = tickAt(
            e.clientY - box.top,
            box.height,
            scanIndices,
            depth,
            index,
        );
        if (hit === null) return;
        // Keeps the slider from also moving to the press.
        e.stopPropagation();
        e.preventDefault();
        viewerContext.setIndex(hit);
    }
</script>

{#snippet numberLine(buttons: boolean)}
    {#each numbers as item, i (item.kind === "link" ? `l-${item.scanNr}` : `e-${i}`)}
        {#if item.kind === "ellipsis"}
            <span class="dim">…</span>
        {:else if buttons}
            <button
                type="button"
                tabindex="-1"
                aria-label="Go to {word} {item.scanNr + 1}"
                aria-current={item.scanNr === index ? "true" : undefined}
                class:current={item.scanNr === index}
                onclick={() => viewerContext.setIndex(item.scanNr)}
            >
                {item.scanNr + 1}
            </button>
        {:else}
            <span class="number">{item.scanNr + 1}</span>
        {/if}
    {/each}
{/snippet}

<div class="edge viewport-overlay">
    <div class="line">
        <div class="measure" aria-hidden="true">
            <span data-part="numbers" bind:offsetWidth={numbersWidth}
                >{@render numberLine(false)}</span
            >
            <span data-part="count" bind:offsetWidth={countWidth}
                >{countText}</span
            >
            <span data-part="word" bind:offsetWidth={wordWidth}
                >{word}&nbsp;</span
            >
            <span data-part="readout" bind:offsetWidth={readoutWidth}
                >{index + 1} / {depth}</span
            >
        </div>
        {#if showCount && parts.count}
            <span class="dim">{countText}</span>
        {/if}
        {#if parts.numbers}
            <span class="numbers">{@render numberLine(true)}</span>
        {/if}
        <span class="readout"
            >{parts.word ? `${word} ` : ""}{index + 1} / {depth}</span
        >
        <IconButton
            size="icon-xs"
            label="Lock slice scrolling"
            aria-pressed={viewerContext.lockScroll}
            class={viewerContext.lockScroll
                ? "bg-background-selected"
                : undefined}
            onclick={() =>
                (viewerContext.lockScroll = !viewerContext.lockScroll)}
        >
            {#if viewerContext.lockScroll}<Locked />{:else}<Unlocked />{/if}
        </IconButton>
    </div>
    <div class="track" bind:this={track} {onpointerdowncapture}>
        <Slider
            orientation="vertical"
            fill={false}
            min={0}
            max={depth - 1}
            oncommit={() => viewerContext.returnFocus()}
            labels={["Slice"]}
            valueTexts={[
                `${word} ${index + 1} of ${depth}${scanIndices.includes(index) ? ", has segmentation" : ""}`,
            ]}
            values={[index]}
            onchange={([slice]) => viewerContext.setIndex(slice)}
        />
        <div class="ticks" aria-hidden="true">
            {#each scanIndices as slice (slice)}
                <span
                    class="tick"
                    title="{word} {slice + 1}"
                    style="top: {tickPercent(slice, depth)}%"
                ></span>
            {/each}
        </div>
    </div>
</div>

<style>
    .edge {
        position: relative;
        flex: none;
        width: 14px;
        background: color-mix(
            in srgb,
            var(--color-background) 75%,
            transparent
        );
    }
    /* Inset by the handle's radius, so the handle stays inside the edge at both ends. */
    .track {
        position: absolute;
        inset: 7px 0;
    }
    .ticks {
        position: absolute;
        inset: 0;
        pointer-events: none;
    }
    .tick {
        position: absolute;
        left: 0;
        width: 100%;
        height: 6px;
        margin-top: -3px;
        pointer-events: auto;
        cursor: pointer;
        background: linear-gradient(
                var(--color-support-warning),
                var(--color-support-warning)
            )
            center / 100% 2px no-repeat;
    }
    .line {
        position: absolute;
        top: 0.25rem;
        right: calc(100% + 0.25rem);
        z-index: 1;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        height: 1.5rem;
        padding-inline-start: 0.25rem;
        white-space: nowrap;
        font-size: var(--text-label-01);
        font-variant-numeric: tabular-nums;
        background: color-mix(
            in srgb,
            var(--color-background) 78%,
            transparent
        );
    }
    .measure {
        position: absolute;
        visibility: hidden;
        pointer-events: none;
        display: flex;
    }
    .numbers {
        display: flex;
        align-items: center;
    }
    .dim {
        padding-inline: 0.125rem;
        color: var(--color-text-secondary);
    }
    .number,
    .numbers button {
        padding-inline: 0.1875rem;
    }
    .numbers button {
        cursor: pointer;
        color: var(--color-link-primary);
    }
    .numbers button.current {
        background: var(--color-layer-selected-inverse);
        color: var(--color-text-inverse);
    }
    .readout {
        color: var(--color-text-primary);
    }
</style>
