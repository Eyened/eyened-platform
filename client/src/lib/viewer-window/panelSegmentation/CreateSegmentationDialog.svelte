<script lang="ts">
	import { Button } from "$lib/components/ui/button";
	import { features } from "$lib/data";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import type { AbstractImage } from "$lib/webgl/abstractImage";
	import { getContext } from "svelte";
	import { toast } from "svelte-sonner";
	import FeatureSelect from "./FeatureSelect.svelte";
	import type { SegmentationContext } from "./segmentationContext.svelte";
	import {
		createSegmentationFromDialog,
		defaultRegionSize,
		isMultiSegmentationType,
		SEGMENTATION_TYPE_OPTIONS,
		type CreateSegmentationDialogMode,
		type SegmentationTypeChoice,
	} from "./createSegmentationHelpers";
	import type { FeatureGET } from "../../../types/openapi_types";
	import type { ImageBox } from "./segmentationRegion";

	interface Props {
		image: AbstractImage;
		axis: number;
		segmentationContext: SegmentationContext;
		subtaskId?: number;
		initialMode?: CreateSegmentationDialogMode;
		box?: ImageBox;
		close: () => void;
	}

	let {
		image,
		axis,
		segmentationContext,
		subtaskId,
		initialMode = "full",
		box: regionBoxProp,
		close,
	}: Props = $props();

	const globalContext = getContext<GlobalContext>("globalContext");
	const taskContext = getContext<TaskContext>("taskContext");

	let mode = $state<CreateSegmentationDialogMode>(initialMode);
	let selectedType = $state<SegmentationTypeChoice>("Q");

	let segWidth = $state(image.width);
	let segHeight = $state(image.height);

	let selectedFeature = $state<FeatureGET | undefined>(undefined);
	let selectedFeatureId = $state("");

	$effect(() => {
		if (regionBoxProp) {
			mode = "region";
			const { width, height } = defaultRegionSize(regionBoxProp);
			segWidth = width;
			segHeight = height;
		}
	});

	$effect(() => {
		if (isMultiSegmentationType(selectedType) && mode === "region") {
			mode = "full";
		}
	});

	const regionDisplay = $derived.by(() => {
		if (!regionBoxProp) return null;
		return {
			x0: Math.round(regionBoxProp.x0),
			y0: Math.round(regionBoxProp.y0),
			x1: Math.round(regionBoxProp.x1),
			y1: Math.round(regionBoxProp.y1),
			imageW: Math.round(regionBoxProp.x1 - regionBoxProp.x0),
			imageH: Math.round(regionBoxProp.y1 - regionBoxProp.y0),
		};
	});

	const allFeatures = $derived(features.map((f) => f));
	const parentFeatures = $derived(
		features.filter((f) => (f.subfeatures ?? []).length > 0),
	);
	const availableFeatures = $derived(
		isMultiSegmentationType(selectedType) ? parentFeatures : allFeatures,
	);

	const placementLockedToFull = $derived(isMultiSegmentationType(selectedType));
	const canCreate = $derived(selectedFeature != null);

	$effect(() => {
		if (
			selectedFeature &&
			!availableFeatures.some((f) => f.id === selectedFeature!.id)
		) {
			selectedFeature = undefined;
			selectedFeatureId = "";
		}
	});

	function selectFeature(feature: FeatureGET) {
		selectedFeature = feature;
		selectedFeatureId = String(feature.id);
	}

	function onNativeSelectChange() {
		if (!selectedFeatureId) {
			selectedFeature = undefined;
			return;
		}
		const feature = availableFeatures.find(
			(f) => String(f.id) === selectedFeatureId,
		);
		if (feature) {
			selectFeature(feature);
		}
	}

	function dismiss() {
		segmentationContext.pendingRegionBox = undefined;
		segmentationContext.regionToolActive = false;
		close();
	}

	function startRegionDraw() {
		segmentationContext.pendingRegionBox = undefined;
		segmentationContext.regionToolActive = true;
		close();
	}

	async function submitCreate() {
		if (!selectedFeature) return;

		if (mode === "region" && !regionBoxProp && !isMultiSegmentationType(selectedType)) {
			toast.error("Draw a region on the image first, or choose full image.");
			return;
		}

		const snapshotBox = regionBoxProp
			? {
					x0: regionBoxProp.x0,
					y0: regionBoxProp.y0,
					x1: regionBoxProp.x1,
					y1: regionBoxProp.y1,
				}
			: undefined;

		segmentationContext.pendingRegionBox = undefined;
		segmentationContext.regionToolActive = false;

		try {
			await createSegmentationFromDialog(globalContext, segmentationContext, {
				image,
				axis,
				feature: selectedFeature,
				subtaskId: subtaskId ?? taskContext?.subTask?.id,
				type: selectedType,
				mode: isMultiSegmentationType(selectedType) ? "full" : mode,
				box:
					mode === "region" && !isMultiSegmentationType(selectedType)
						? snapshotBox
						: undefined,
				segWidth,
				segHeight,
			});
			close();
		} catch {
			// toast shown in helper
		}
	}
</script>

<div class="dialog">
	<h3>New segmentation</h3>
	<p class="hint">Choose placement, type, and feature, then click Create.</p>

	<fieldset class="section">
		<legend>Placement</legend>
		<div class="radio-row">
			<label class="radio-option">
				<input
					type="radio"
					name="placement"
					value="full"
					bind:group={mode}
					disabled={placementLockedToFull}
				/>
				Full image
			</label>
			<label class="radio-option">
				<input
					type="radio"
					name="placement"
					value="region"
					bind:group={mode}
					disabled={placementLockedToFull}
				/>
				Region box
			</label>
		</div>
		{#if placementLockedToFull}
			<p class="coords muted">Multi-class and multi-label use the full image.</p>
		{/if}

		{#if mode === "region" && !placementLockedToFull}
			{#if regionDisplay}
				<p class="coords">
					Image box: ({regionDisplay.x0}, {regionDisplay.y0}) → ({regionDisplay.x1},
					{regionDisplay.y1})
					<span class="dim"
						>({regionDisplay.imageW} × {regionDisplay.imageH} px on image)</span
					>
				</p>
				<Button variant="secondary" size="sm" onclick={startRegionDraw}>
					Redraw region on image…
				</Button>
			{:else}
				<p class="coords muted">No region drawn yet.</p>
				<Button variant="secondary" size="sm" onclick={startRegionDraw}>
					Draw region on image…
				</Button>
			{/if}
			<div class="row">
				<label>
					Seg. width
					<input type="number" min="1" bind:value={segWidth} />
				</label>
				<label>
					Seg. height
					<input type="number" min="1" bind:value={segHeight} />
				</label>
			</div>
		{:else if !placementLockedToFull}
			<p class="coords muted">
				Covers the full image ({image.width} × {image.height} px).
			</p>
		{/if}
	</fieldset>

	<fieldset class="section">
		<legend>Type & feature</legend>

		<div class="radio-column">
			{#each SEGMENTATION_TYPE_OPTIONS as opt}
				<label class="radio-option">
					<input
						type="radio"
						name="seg-type"
						value={opt.value}
						bind:group={selectedType}
					/>
					{opt.label}
				</label>
			{/each}
		</div>

		{#if isMultiSegmentationType(selectedType)}
			<p class="coords muted">
				Parent features with subfeatures only ({availableFeatures.length} available).
			</p>
		{/if}

		<FeatureSelect
			values={availableFeatures}
			selectedName={selectedFeature?.name ?? ""}
			onselect={selectFeature}
		/>

		<label class="select-label">
			<span>Or select feature</span>
			<select
				class="native-select"
				bind:value={selectedFeatureId}
				onchange={onNativeSelectChange}
			>
				<option value="">—</option>
				{#each availableFeatures as f (f.id)}
					<option value={String(f.id)}>{f.name}</option>
				{/each}
			</select>
		</label>
	</fieldset>

	<div class="footer">
		<Button variant="outline" size="sm" onclick={dismiss}>Cancel</Button>
		<Button variant="default" size="sm" disabled={!canCreate} onclick={submitCreate}>
			Create
		</Button>
	</div>
</div>

<style>
	.dialog {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		min-width: 320px;
		max-width: 480px;
		max-height: min(85vh, 640px);
		overflow-y: auto;
		padding: 0.25rem;
	}
	h3 {
		margin: 0;
		font-size: 1.05rem;
	}
	.hint {
		margin: 0;
		font-size: 0.85em;
		opacity: 0.8;
	}
	.section {
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 0.35rem;
		padding: 0.6rem 0.75rem;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	legend {
		font-size: 0.8em;
		font-weight: 600;
		padding: 0 0.25em;
		opacity: 0.9;
	}
	.radio-row {
		display: flex;
		flex-direction: row;
		flex-wrap: wrap;
		gap: 0.75rem 1.25rem;
		align-items: center;
	}
	.radio-column {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.radio-option {
		display: flex;
        flex-direction: row;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.9em;
		cursor: pointer;
	}
	.coords {
		margin: 0;
		font-size: 0.85em;
	}
	.coords.muted {
		opacity: 0.75;
	}
	.dim {
		display: block;
		margin-top: 0.2em;
	}
	.row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: flex-end;
	}
	label {
		display: flex;
		flex-direction: column;
		font-size: 0.8em;
		gap: 0.15em;
	}
	.select-label {
		gap: 0.25em;
	}
	input[type="number"] {
		width: 5em;
	}
	.native-select {
		width: 100%;
		box-sizing: border-box;
		font-size: 0.9em;
		color: rgba(255, 255, 255, 0.9);
		background-color: rgba(255, 255, 255, 0.15);
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 0.25rem;
		padding: 0.35em 0.5em;
	}
	.footer {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		padding-top: 0.25rem;
	}
</style>
