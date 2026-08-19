<script lang="ts">
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import {
        BSCAN_LINKS_SHOW_ALL_MAX,
        buildBscanDisplayItems,
    } from "./bscanLinksDisplay";

    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const segmentationContext = mainViewerContext.segmentationContext;
    const scanIndices = $derived(segmentationContext.scan_indices);

    const viewerContext = getContext<ViewerContext>("viewerContext");

    const displayItems = $derived(
        buildBscanDisplayItems(scanIndices, viewerContext.index),
    );
    const isWindowed = $derived(scanIndices.length > BSCAN_LINKS_SHOW_ALL_MAX);

    async function activateScanNr(e: MouseEvent, scanNr: number) {
        e.stopPropagation();
        const lock = viewerContext.lockScroll;
        viewerContext.lockScroll = false;
        viewerContext.setIndex(scanNr);
        setTimeout(() => (viewerContext.lockScroll = lock), 0);
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="row links">
    {#if scanIndices.length > 0}
        {#if isWindowed}
            <span
                class="summary"
                title="{scanIndices.length} B-scans with segmentation data — scroll to update nearby links"
            >
                {scanIndices.length} B-scans
            </span>
            <span class="sep">|</span>
        {/if}
        {#each displayItems as item, i (item.kind === "link" ? `l-${item.scanNr}` : `e-${i}`)}
            {#if i > 0}
                <span class="sep">|</span>
            {/if}
            {#if item.kind === "ellipsis"}
                <span class="ellipsis" aria-hidden="true">…</span>
            {:else}
                <span
                    class="link-scan"
                    class:active={item.scanNr === viewerContext.index}
                    onclick={(e) => activateScanNr(e, item.scanNr)}
                >
                    {item.scanNr}
                </span>
            {/if}
        {/each}
    {/if}
</div>

<style>
    div.row {
        flex-direction: row;
        flex: 1;
        width: 100%;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.1em 0;
    }
    div.links {
        font-size: x-small;
        max-width: 100%;
    }
    .summary {
        opacity: 0.75;
        white-space: nowrap;
    }
    .sep {
        opacity: 0.45;
        padding: 0 0.15em;
        user-select: none;
    }
    .ellipsis {
        opacity: 0.5;
        padding: 0 0.25em;
        user-select: none;
    }
    .link-scan {
        padding: 0 0.35em;
        cursor: pointer;
        white-space: nowrap;
    }
    .link-scan.active {
        text-decoration: underline;
        font-weight: 600;
    }
    .link-scan:hover {
        color: white;
    }
</style>
