<script lang="ts">
	import { Button } from "$lib/components/ui/button";
	import { createSegmentationFrom, features } from "$lib/data";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type {
		FeatureGET,
		SegmentationDataRepresentation,
		SegmentationDataType,
	} from "../../../types/openapi_types";
	import type { AbstractImage } from "$lib/webgl/abstractImage";
	import { getContext } from "svelte";
	import { toast } from "svelte-sonner";
	import FeatureSelect from "./FeatureSelect.svelte";
	import type { SegmentationContext } from "./segmentationContext.svelte";
	import {
		imageBoxHeight,
		imageBoxWidth,
		projectionMatrixFromBox,
		type ImageBox,
	} from "./segmentationRegion";

	interface Props {
		box: ImageBox;
		image: AbstractImage;
		axis: number;
		segmentationContext: SegmentationContext;
		subtaskId?: number;
		close: () => void;
	}
	let { box, image, axis, segmentationContext, subtaskId, close }: Props = $props();

	const globalContext = getContext<GlobalContext>("globalContext");

	const types = ["Q", "B", "P"] as const;
	let selectedType = $state<(typeof types)[number]>("Q");
	const dataRepresentations: Record<(typeof types)[number], SegmentationDataRepresentation> = {
		Q: "DualBitMask",
		B: "Binary",
		P: "Probability",
	};

	let segWidth = $state(0);
	let segHeight = $state(0);
	$effect(() => {
		segWidth = imageBoxWidth(box);
		segHeight = imageBoxHeight(box);
	});

	const dataRepresentationsDisplay = $derived({
		x0: Math.round(box.x0),
		y0: Math.round(box.y0),
		x1: Math.round(box.x1),
		y1: Math.round(box.y1),
		imageW: Math.round(box.x1 - box.x0),
		imageH: Math.round(box.y1 - box.y0),
	});

	function dismiss() {
		segmentationContext.pendingRegionBox = undefined;
		close();
	}

	async function create(feature: FeatureGET) {
		// Snapshot everything before changing dialogue (unmounts this component and clears props).
		const snapshotImage = image;
		const snapshotAxis = axis;
		const snapshotSubtaskId = subtaskId;
		const snapshotContext = segmentationContext;
		const snapshotBox = { x0: box.x0, y0: box.y0, x1: box.x1, y1: box.y1 };
		const w = Math.max(1, Math.round(segWidth));
		const h = Math.max(1, Math.round(segHeight));
		const depth = snapshotImage.depth;
		const type = selectedType;
		const featureId = feature.id;

		snapshotContext.pendingRegionBox = undefined;

		globalContext.dialogue = `Creating annotation...`;
		try {
			let dataType: SegmentationDataType = "R8UI";
			if (type === "P") {
				dataType = "R8";
			}
			const matrix = projectionMatrixFromBox(snapshotBox, w, h);
			const segmentation = await createSegmentationFrom(
				snapshotImage,
				featureId,
				dataRepresentations[type],
				dataType,
				0.5,
				snapshotAxis,
				snapshotSubtaskId,
				{
					shape: {
						depth,
						height: h,
						width: w,
					},
					image_projection_matrix: matrix,
				},
			);
			snapshotContext.segmentationItem =
				snapshotContext.getSegmentationItem(segmentation);
			close();
		} catch (err) {
			console.error(err);
			toast.error(err instanceof Error ? err.message : "Could not create annotation");
		} finally {
			globalContext.dialogue = null;
		}
	}
</script>

<div class="dialog">
	<h3>New segmentation region</h3>
	<p class="coords">
		Image box: ({dataRepresentationsDisplay.x0}, {dataRepresentationsDisplay.y0}) →
		({dataRepresentationsDisplay.x1}, {dataRepresentationsDisplay.y1})
		<span class="dim">({dataRepresentationsDisplay.imageW} × {dataRepresentationsDisplay.imageH} px)</span>
	</p>
	<div class="row">
		<label>
			Width
			<input type="number" min="1" bind:value={segWidth} />
		</label>
		<label>
			Height
			<input type="number" min="1" bind:value={segHeight} />
		</label>
	</div>
	<div class="row type">
		<span>Type:</span>
		{#each types as type}
			<label>
				<input type="radio" name="region-type" value={type} bind:group={selectedType} />
				{type}
			</label>
		{/each}
	</div>
	<FeatureSelect values={features.map((f) => f)} onselect={create} />
	<Button variant="outline" size="sm" onclick={dismiss}>Cancel</Button>
</div>

<style>
	.dialog {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		min-width: 280px;
		max-width: 420px;
		padding: 0.25rem;
	}
	h3 {
		margin: 0;
		font-size: 1rem;
	}
	.coords {
		margin: 0;
		font-size: 0.85em;
		opacity: 0.85;
	}
	.dim {
		display: block;
		margin-top: 0.25em;
	}
	.row {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.row.type {
		gap: 0.5rem;
	}
	label {
		display: flex;
		flex-direction: column;
		font-size: 0.85em;
		gap: 0.2em;
	}
	input[type="number"] {
		width: 5em;
	}
</style>
