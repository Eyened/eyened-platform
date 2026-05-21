<script lang="ts">
	import { Button } from "$lib/components/ui/button";
	import { createSegmentationFrom, features } from "$lib/data";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type {
		FeatureGET,
		SegmentationDataRepresentation,
		SegmentationDataType,
	} from "../../../types/openapi_types";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext } from "svelte";
	import { toast } from "svelte-sonner";
	import FeatureSelect from "./FeatureSelect.svelte";
	import { projectionMatrixFromScaleTranslate } from "./segmentationRegion";

	const globalContext = getContext<GlobalContext>("globalContext");
	const viewerContext = getContext<ViewerContext>("viewerContext");
	const taskContext = getContext<TaskContext>("taskContext");
	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
	const { image, axis } = viewerContext;
	const segmentationContext = mainViewerContext.segmentationContext;

	const types = ["Q", "B", "P"] as const;
	let selectedType = $state<(typeof types)[number]>("Q");
	let expanded = $state(false);

	let segWidth = $state(512);
	let segHeight = $state(512);
	let scale = $state(1);
	let tx = $state(0);
	let ty = $state(0);

	const dataRepresentations: Record<(typeof types)[number], SegmentationDataRepresentation> = {
		Q: "DualBitMask",
		B: "Binary",
		P: "Probability",
	};

	async function create(feature: FeatureGET) {
		globalContext.dialogue = `Creating annotation...`;
		try {
			let dataType: SegmentationDataType = "R8UI";
			if (selectedType === "P") {
				dataType = "R8";
			}
			const matrix = projectionMatrixFromScaleTranslate(scale, tx, ty);
			const segmentation = await createSegmentationFrom(
				image,
				feature.id,
				dataRepresentations[selectedType],
				dataType,
				0.5,
				axis,
				taskContext?.subTask?.id,
				{
					shape: {
						depth: image.depth,
						height: Math.max(1, Math.round(segHeight)),
						width: Math.max(1, Math.round(segWidth)),
					},
					image_projection_matrix: matrix,
				},
			);
			segmentationContext.segmentationItem =
				segmentationContext.getSegmentationItem(segmentation);
		} catch (err) {
			console.error(err);
			toast.error(err instanceof Error ? err.message : "Could not create annotation");
		} finally {
			globalContext.dialogue = null;
		}
	}
</script>

<div class="manual">
	<Button variant="outline" size="sm" onclick={() => (expanded = !expanded)}>
		{expanded ? "▼" : "►"} Custom size / matrix
	</Button>
	{#if expanded}
		<div class="fields">
			<label>Width <input type="number" min="1" bind:value={segWidth} /></label>
			<label>Height <input type="number" min="1" bind:value={segHeight} /></label>
			<label>Scale <input type="number" step="0.01" bind:value={scale} /></label>
			<label>tx <input type="number" step="1" bind:value={tx} /></label>
			<label>ty <input type="number" step="1" bind:value={ty} /></label>
		</div>
		<div class="type">
			<span>Type:</span>
			{#each types as type}
				<label>
					<input type="radio" name="manual-type" value={type} bind:group={selectedType} />
					{type}
				</label>
			{/each}
		</div>
		<p class="hint">Matrix: scale on diagonal, translation (tx, ty). Pick feature below.</p>
		<FeatureSelect values={features} onselect={create} />
	{/if}
</div>

<style>
	.manual {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.fields {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	label {
		display: flex;
		flex-direction: column;
		font-size: 0.8em;
		gap: 0.15em;
	}
	input[type="number"] {
		width: 4.5em;
	}
	.type {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		font-size: 0.85em;
	}
	.hint {
		margin: 0;
		font-size: 0.75em;
		opacity: 0.7;
	}
</style>
