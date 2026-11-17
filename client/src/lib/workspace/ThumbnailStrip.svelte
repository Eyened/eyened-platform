<!--
@component
The thumbnail strip: one live tile per catalogue image, in catalogue order, scrolling sideways.
One tab stop for the tiles (plus that tile's Copy): ← → move between tiles, Home / End go to the ends, Enter or Space loads.
Each tile's Copy public ID bar shows on hover or while focus is inside the tile; its button takes Tab only in the tile that holds the tab stop.
Click or Enter loads into the selected viewport; drag loads onto any viewport. Tiles never write the shared pointer.
-->
<script lang="ts">
    import {
        getContext,
        onDestroy,
        setContext,
        tick,
        type Snippet,
    } from "svelte";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { copyToClipboard } from "$lib/utils/copyToClipboard";
    import { instanceIdFromImageId } from "$lib/viewer-window/viewerViewState";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
    import { IMAGE_MIME } from "./dragTypes";
    import { titleText, type ViewportTitle } from "./imageMeta";
    import { rovingIndex } from "./rovingIndex";
    import type { Workspace } from "./workspace.svelte";

    let {
        tile,
        titleFor,
    }: {
        tile: Snippet<[string]>;
        titleFor: (imageId: string) => ViewportTitle | null;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    let strip: HTMLElement | undefined = $state();
    /** The last focused tile; the tab stop falls back to the first tile. */
    let focusId: string | null = $state(null);
    const tabStop = $derived(
        focusId !== null && workspace.catalogue.includes(focusId)
            ? focusId
            : workspace.catalogue[0],
    );

    // Tile viewers clip their drawing to the strip, so a tile scrolled out of view draws nothing.
    setContext("viewportClip", () => strip?.getBoundingClientRect() ?? null);

    /** 1-based numbers of the slots showing each image. */
    const slotNumbers = $derived(
        workspace.slots.reduce<Record<string, number[]>>(
            (out, slot, i) =>
                slot.imageId
                    ? {
                          ...out,
                          [slot.imageId]: [...(out[slot.imageId] ?? []), i + 1],
                      }
                    : out,
            {},
        ),
    );

    /** The tile whose public ID was copied in the last 2 s. */
    let copiedId: string | null = $state(null);
    let announcement = $state("");
    let copiedTimer: ReturnType<typeof setTimeout> | undefined;
    onDestroy(() => clearTimeout(copiedTimer));

    // Carbon CopyButton feedback for 2 s. The click must not reach the tile, which loads.
    async function copy(e: MouseEvent, imageId: string) {
        e.stopPropagation();
        if (!(await copyToClipboard(instanceIdFromImageId(imageId)))) return;
        clearTimeout(copiedTimer);
        copiedId = imageId;
        // Blank the live region first, so a repeat copy is announced again.
        announcement = "";
        await tick();
        announcement = "Copied";
        copiedTimer = setTimeout(() => {
            copiedId = null;
            announcement = "";
        }, 2000);
    }

    function ondragstart(e: DragEvent, imageId: string) {
        if (!e.dataTransfer) return;
        e.dataTransfer.setData(IMAGE_MIME, imageId);
        e.dataTransfer.effectAllowed = "copy";
    }

    // Enter and Space are the button's own click, which the tile handles.
    async function onkeydown(e: KeyboardEvent, i: number) {
        const next = rovingIndex(e.key, i, workspace.catalogue.length, {
            prev: ["ArrowLeft"],
            next: ["ArrowRight"],
        });
        if (next === null) return;
        e.preventDefault();
        focusId = workspace.catalogue[next];
        await tick();
        strip
            ?.querySelector<HTMLElement>(`[data-tile-index="${next}"]`)
            ?.focus();
    }
</script>

<ul bind:this={strip} class="strip" aria-label="Thumbnails">
    {#each workspace.catalogue as imageId, i (imageId)}
        {@const title = titleFor(imageId)}
        {@const slots = slotNumbers[imageId]}
        <!-- ASSUMPTION: a click on the tile's image is a shortcut for its button (plan decision 21). -->
        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
        <li
            class="tile"
            onclick={() => workspace.load(workspace.selected, imageId)}
        >
            <button
                type="button"
                draggable="true"
                class="tile-title"
                data-tile-index={i}
                tabindex={imageId === tabStop ? 0 : -1}
                onfocus={() => (focusId = imageId)}
                onkeydown={(e) => onkeydown(e, i)}
                ondragstart={(e) => ondragstart(e, imageId)}
            >
                {#if slots}
                    <span class="slot"
                        ><span class="sr-only">In viewport </span>{slots.join(
                            ", ",
                        )}</span
                    >
                {/if}
                <span class="title">{title ? titleText(title) : imageId}</span>
            </button>
            <div class="tile-body">
                {@render tile(imageId)}
                <div class="copy-bar">
                    <span class="public-id"
                        >{instanceIdFromImageId(imageId)}</span
                    >
                    <IconButton
                        label="Copy public ID"
                        tooltip={copiedId === imageId ? "Copied" : undefined}
                        size="icon-xs"
                        closeOnClick={false}
                        tabindex={imageId === tabStop ? 0 : -1}
                        onclick={(e) => copy(e, imageId)}
                        onpointerdown={(e) => e.stopPropagation()}
                    >
                        <Copy />
                    </IconButton>
                </div>
            </div>
        </li>
    {/each}
</ul>
<p class="sr-only" aria-live="polite">{announcement}</p>

<style>
    .strip {
        display: flex;
        flex: none;
        gap: 2px;
        height: 104px;
        overflow-x: auto;
        overflow-y: hidden;
    }
    .tile {
        /* Keeps the sr-only label inside the scrolled strip. */
        position: relative;
        display: flex;
        flex: none;
        flex-direction: column;
        width: 132px;
        box-shadow: 0 0 0 1px var(--color-border-subtle-01);
    }
    .tile-title {
        display: flex;
        flex: none;
        gap: 0.25rem;
        height: 1.5rem;
        padding-inline: 0.5rem;
        background: var(--color-layer-01);
        font-size: var(--text-label-01);
        line-height: 1.5rem;
        white-space: nowrap;
        text-align: start;
        cursor: grab;
    }
    .slot {
        flex: none;
        color: var(--color-text-primary);
    }
    .title {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        color: var(--color-text-secondary);
    }
    .tile-body {
        position: relative;
        display: flex;
        flex: 1;
        min-height: 0;
    }
    /* Development's hover bar, also shown while focus is inside the tile; solid, so text and icon keep their contrast over a light image. */
    .copy-bar {
        position: absolute;
        top: 0.25rem;
        right: 0.25rem;
        z-index: 1;
        display: flex;
        align-items: center;
        gap: 0.25rem;
        max-width: calc(100% - 0.5rem);
        padding-inline-start: 0.5rem;
        background: var(--color-background);
        color: var(--color-text-primary);
        font-size: var(--text-label-01);
        opacity: 0;
        pointer-events: none;
    }
    .tile:hover .copy-bar,
    .tile:focus-within .copy-bar {
        opacity: 1;
        pointer-events: auto;
    }
    .public-id {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
</style>
