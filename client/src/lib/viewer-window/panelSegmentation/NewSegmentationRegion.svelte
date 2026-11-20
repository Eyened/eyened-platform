<script lang="ts">
    import { SegmentationRegionTool } from "$lib/viewer/tools/SegmentationRegionTool";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onDestroy } from "svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const segmentationContext = mainViewerContext.segmentationContext;

    const regionTool = new SegmentationRegionTool(
        viewerContext,
        segmentationContext,
    );
    let removeOverlay = () => {};

    $effect(() => {
        if (segmentationContext.regionToolActive) {
            removeOverlay = viewerContext.addOverlay(regionTool);
        } else {
            removeOverlay();
            removeOverlay = () => {};
            regionTool.deactivate();
        }
    });

    onDestroy(() => {
        removeOverlay();
        segmentationContext.regionToolActive = false;
        // A section remounted for another viewport must not reopen a stale modal.
        segmentationContext.createDialog = null;
    });
</script>
