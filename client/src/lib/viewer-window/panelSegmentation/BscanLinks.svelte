<script lang="ts">
    import { getContext } from "svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";

    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const segmentationContext = segmentationOverlay.segmentationContext;
    let segmentation = $derived(
        segmentationContext.segmentationItem?.segmentation,
    );

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const image = viewerContext.image;
    const registration = viewerContext.registration;

    async function activateScanNr(e: MouseEvent, scanNr: number) {
        e.stopPropagation();
        // override the lockScroll while setting the position
        const lock = viewerContext.lockScroll;
        viewerContext.lockScroll = false;
        registration.setPosition(image.image_id, { x: 0, y: 0, index: scanNr });
        setTimeout(() => (viewerContext.lockScroll = lock), 0);
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="row links">
    {#if segmentation}
        {#each segmentation.scanIndices as scanNr, i (scanNr)}
            {#if i > 0}|{/if}
            <span
                class="link-scan"
                class:active={scanNr == viewerContext.index}
                onclick={(e) => activateScanNr(e, scanNr)}
            >
                {scanNr}
            </span>
        {/each}
    {/if}
</div>

<style>
    div.row {
        flex-direction: row;
        flex: 1;
        width: 100%;
    }
    div.links {
        font-size: x-small;
    }
    .link-scan {
        padding: 0 0.4em;
        cursor: pointer;
    }
    .link-scan.active {
        text-decoration: underline;
    }
    .link-scan:hover {
        color: white;
    }
</style>
