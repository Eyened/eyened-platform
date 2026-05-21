<script lang="ts">
	import { Button } from "$lib/components/ui/button";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { features } from "$lib/data";
	import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import { getContext } from "svelte";
	import type { FeatureGET } from "../../../types/openapi_types";
	import FeatureSelect from "./FeatureSelect.svelte";
	import CreateSegmentationDialog from "./CreateSegmentationDialog.svelte";
	import { createQuestionableSegmentation } from "./createSegmentationHelpers";
	import NewSegmentationRegion from "./NewSegmentationRegion.svelte";

	const globalContext = getContext<GlobalContext>("globalContext");
	const viewerContext = getContext<ViewerContext>("viewerContext");
	const taskContext = getContext<TaskContext>("taskContext");
	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
	const segmentationContext = mainViewerContext.segmentationContext;
	const { image, axis } = viewerContext;

	async function createQuestionable(feature: FeatureGET) {
		await createQuestionableSegmentation(
			globalContext,
			segmentationContext,
			image,
			axis,
			feature,
			taskContext?.subTask?.id,
		);
	}

	function openAdvanced() {
		globalContext.dialogue = {
			component: CreateSegmentationDialog,
			props: {
				image,
				axis,
				segmentationContext,
				subtaskId: taskContext?.subTask?.id,
				initialMode: "full",
			},
		};
	}
</script>

<div class="new">
	<p class="label">Search feature to create</p>
	<FeatureSelect values={features.map((f) => f)} onselect={createQuestionable} />
	<Button variant="outline" size="sm" class="advanced-btn" onclick={openAdvanced}>
		Advanced…
	</Button>
</div>

<!-- Region tool + dialog when box is drawn (no panel chrome). -->
<NewSegmentationRegion />

<style>
	.new {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding-top: 0.5rem;
		border-top: 1px solid rgba(255, 255, 255, 0.15);
	}
	.label {
		margin: 0;
		font-size: 0.8em;
		opacity: 0.75;
	}
	.advanced-btn {
		align-self: flex-start;
	}
</style>
