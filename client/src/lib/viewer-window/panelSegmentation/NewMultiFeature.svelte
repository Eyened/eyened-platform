<script lang="ts">
	import { Button } from "$lib/components/ui/button";
	import { createSegmentationFrom, features } from "$lib/data";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type { Datatype } from "$lib/datamodel/segmentation.svelte";
	import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext } from "svelte";
	import * as Select from "../../components/ui/select";

	const viewerContext = getContext<ViewerContext>("viewerContext");
	const { image, axis } = viewerContext;
	const globalContext = getContext<GlobalContext>("globalContext");
	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
	const segmentationContext = mainViewerContext.segmentationContext;
	const { user: creator } = globalContext;

	// Use repo to drive the UI list of parents-with-subfeatures
	const featuresWithSubfeatures = $derived(
		features.filter((f) => (f.subfeatures ?? []).length > 0),
	);

	let selectedFeatureId: number | false = $state(false);
	async function create(dataRepresentation: "MultiLabel" | "MultiClass") {
		if (selectedFeatureId == false) {
			return;
		}
		globalContext.dialogue = `Creating annotation...`;

		let dataType: Datatype = "R8UI";

		await createSegmentationFrom(
			image,
			selectedFeatureId,
			dataRepresentation,
			dataType,
			0.5,
			axis,
		);
		segmentationContext.creatorHidden.set(creator.id, false);

		globalContext.dialogue = null;
	}
</script>

<div class="multi">
	<Select.Root type="single" bind:value={selectedFeatureId} size="xs">
		<Select.Trigger class="w-[180px]">
			{selectedFeatureId
				? featuresWithSubfeatures.find((f) => f.id === selectedFeatureId)?.name
				: "Select feature"}
		</Select.Trigger>
		<Select.Content>
			{#each featuresWithSubfeatures as f}
				<Select.Item value={f.id}>
					{f.name}
				</Select.Item>
			{/each}
		</Select.Content>
	</Select.Root>
	<Button
		variant="outline"
		disabled={selectedFeatureId == false}
		onclick={() => create("MultiClass")}
	>
		Create MultiClass
	</Button>
	<Button
		variant="outline"
		disabled={selectedFeatureId == false}
		onclick={() => create("MultiLabel")}
	>
		Create MultiLabel
	</Button>
</div>

<style>
	div {
		display: flex;
	}
	div.multi {
		flex-direction: column;
	}
</style>
