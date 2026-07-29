<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { SegmentationRegionTool } from "$lib/viewer/tools/SegmentationRegionTool";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { getContext, onDestroy } from "svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import CreateSegmentationDialog from "./CreateSegmentationDialog.svelte";

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const segmentationContext = mainViewerContext.segmentationContext;
    const { image, axis } = viewerContext;

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

    $effect(() => {
        const box = segmentationContext.pendingRegionBox;
        if (!box) return;
        segmentationContext.pendingRegionBox = undefined;
        const snapshot = { x0: box.x0, y0: box.y0, x1: box.x1, y1: box.y1 };
        globalContext.dialogue = {
            component: CreateSegmentationDialog,
            props: {
                box: snapshot,
                image,
                axis,
                segmentationContext,
                subtaskId: taskContext?.subTask?.id,
                initialMode: "region",
            },
        };
    });

    onDestroy(() => {
        removeOverlay();
        segmentationContext.regionToolActive = false;
    });
</script>
