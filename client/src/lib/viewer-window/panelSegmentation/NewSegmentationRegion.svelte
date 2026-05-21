<script lang="ts">
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { SegmentationRegionTool } from "$lib/viewer/tools/SegmentationRegionTool";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import { getContext, onDestroy } from "svelte";
	import { PanelIcon, RegionBox } from "../icons/icons";
	import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import CreateSegmentationRegionDialog from "./CreateSegmentationRegionDialog.svelte";

	const viewerContext = getContext<ViewerContext>("viewerContext");
	const globalContext = getContext<GlobalContext>("globalContext");
	const taskContext = getContext<TaskContext>("taskContext");
	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
	const segmentationContext = mainViewerContext.segmentationContext;
	const { image, axis } = viewerContext;

	const regionTool = new SegmentationRegionTool(viewerContext, segmentationContext);
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
		if (box) {
			globalContext.dialogue = {
				component: CreateSegmentationRegionDialog,
				props: {
					box,
					image,
					axis,
					segmentationContext,
					subtaskId: taskContext?.subTask?.id,
				},
			};
		}
	});

	onDestroy(() => {
		removeOverlay();
		segmentationContext.regionToolActive = false;
	});

	function toggleRegionTool() {
		segmentationContext.regionToolActive = !segmentationContext.regionToolActive;
	}
</script>

<PanelIcon
	onclick={toggleRegionTool}
	active={segmentationContext.regionToolActive}
	tooltip="Draw region on image (drag box)"
	Icon={RegionBox}
	size={2}
/>
