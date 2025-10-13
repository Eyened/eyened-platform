<script lang="ts">
	import { deleteSegmentation } from "$lib/data/api";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext } from "svelte";
	import { Hide, PanelIcon, Show, Trash } from "../icons/icons";
	import ThresholdSlider from "./ThresholdSlider.svelte";

	import StringDialogue from "$lib/StringDialogue.svelte";
	import AI from "../icons/AI.svelte";
	import { ViewerWindowContext } from "../viewerWindowContext.svelte";
	import CCPanel from "./CCPanel.svelte";
	import { duplicate } from "./duplicate_utils";
	import DuplicateAnnotationPanel from "./DuplicateAnnotationPanel.svelte";
	import FeatureColorPicker from "./FeatureColorPicker.svelte";
	import ImportPanel from "./ImportPanel.svelte";
	import MultiFeatureSelector from "./MultiFeatureSelector.svelte";
	import ReferenceSegmentationPanel from "./ReferenceSegmentationPanel.svelte";
	import type { Segmentation } from "./segmentationContext.svelte";

	const globalContext = getContext<GlobalContext>("globalContext");
	const viewerWindowContext = getContext<ViewerWindowContext>(
		"viewerWindowContext",
	);

	interface Props {
		segmentation: Segmentation;
		style?: "AI" | "normal";
	}

	let { segmentation, style = "normal" }: Props = $props();
	// const segmentationObject =
	//     segmentation.annotation_type == "grader_segmentation" ?
	//     new SegmentationObject(segmentation, viewerWindowContext.Segmentations) :
	//     new ModelSegmentationObject(segmentation, viewerWindowContext.ModelSegmentations);
	const feature = segmentation.feature;
	const dataRepresentation = segmentation.data_representation;

	const viewerContext = getContext<ViewerContext>("viewerContext");

	const image = viewerContext.image;
	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");

	const { segmentationContext } = mainViewerContext;

	const visible = $derived(
		!segmentationContext.hiddenSegmentations.has(segmentation),
	);

	const segmentationItem = segmentationContext.getSegmentationItem(segmentation);
	let segmentationState = $derived(
		segmentationItem.getSegmentationState(viewerContext.index),
	);

	async function removeAnnotation() {
		const resolve = async () => {
			// remove from database on server
			if (segmentation.annotation_type === 'grader_segmentation') {
				await deleteSegmentation(segmentation.id);
			}
			segmentationContext.toggleActive(undefined);
			// segmentationItem.dispose();
		};

		globalContext.dialogue = {
			component: StringDialogue,
			props: {
				query: `Delete segmentation [${segmentation.id}]?`,
				approve: "Delete",
				decline: "Cancel",
				resolve,
			},
		};
	}

	function toggleShow() {
		segmentationContext.toggleShowSegmentation(segmentation);
	}

	function showOnly() {
		segmentationContext.showOnlySegmentation(segmentation);
	}

	const isEditable = globalContext.canEdit(segmentation);
	function activate() {
		segmentationContext.toggleActive(segmentationItem);
	}

	let active = $derived(
		segmentationContext.segmentationItem == segmentationItem,
	);

	let collapsed = $state(true);

	function pointerEnter() {
		mainViewerContext.highlightedSegmentationItem = segmentationItem;
	}

	function pointerLeave() {
		mainViewerContext.highlightedSegmentationItem = undefined;
	}

	const segmentationType = {
		Binary: "B",
		DualBitMask: "Q",
		Probability: "P",
		MultiClass: "MC",
		MultiLabel: "ML",
	}[dataRepresentation];

	function applyDuplicate() {
		duplicate(
			globalContext,
			segmentation,
			segmentationItem,
			image,
			viewerContext,
			false,
			"Q",
			globalContext.user.id,
		);
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="content"
	class:compact={style == "AI"}
	class:normal={style == "normal"}
	class:loading={segmentationItem.loading}
	class:active
	onpointerenter={pointerEnter}
	onpointerleave={pointerLeave}
>
	<div class="row">
		<div>
			{#if visible}
				<PanelIcon
					onclick={toggleShow}
					onrightclick={showOnly}
					tooltip="Hide"
					Icon={Show}
				/>
			{:else}
				<PanelIcon
					onclick={toggleShow}
					onrightclick={showOnly}
					tooltip="Show"
					Icon={Hide}
				/>
			{/if}
		</div>

		{#if !(dataRepresentation == "MultiLabel" || dataRepresentation == "MultiClass")}
			<FeatureColorPicker {segmentation} />
		{/if}

		<div class="expand" onclick={activate}>
			{#if style == "AI"}
				<div class="ai"><AI size="1.2em" /></div>
			{/if}
			<div class="feature-name">{feature.name}</div>
			<div class="segmentationID">[{segmentation.id}]</div>
			<div class="segmentationType">[{segmentationType}]</div>
		</div>

		{#if isEditable}
			<PanelIcon onclick={removeAnnotation} tooltip="Delete" Icon={Trash} />
		{/if}
	</div>

	{#if dataRepresentation == "Probability"}
		{#if active}
			<div class="row">
				<ThresholdSlider {segmentation} />
			</div>
		{/if}
	{/if}
	{#if active && style == "AI"}
		<div class="row">
			<button onclick={applyDuplicate}>Duplicate</button>
		</div>
	{/if}

	{#if dataRepresentation == "MultiLabel" || dataRepresentation == "MultiClass"}
		<MultiFeatureSelector {segmentation} {active} />
	{/if}
	{#if segmentationItem.loading}
		<div class="row">
			<div class="loading">Loading segmentation…</div>
		</div>
	{/if}
	{#if active}
		<div class="open" onclick={() => (collapsed = !collapsed)}>
			{#if collapsed}
				&#9654;
			{:else}
				&#9660;
			{/if}
		</div>

		{#if !collapsed}
			<div class="content">
				{#if isEditable}
					<div class="row">
						<ImportPanel {segmentation} {image} {segmentationItem} />
					</div>
				{/if}
				<div class="row">
					{#if segmentationState}
						<DuplicateAnnotationPanel
							{segmentation}
							{image}
							{segmentationItem}
						/>
					{/if}
				</div>

				<div class="row">
					<ReferenceSegmentationPanel
						{segmentation}
						{image}
						{isEditable}
						{segmentationItem}
					/>
				</div>

				{#if dataRepresentation == "Binary" || dataRepresentation == "DualBitMask"}
					<div class="row">
						<CCPanel {segmentationItem} />
					</div>
				{/if}
			</div>
		{/if}
	{/if}
</div>

<style>
	div {
		display: flex;
	}
	div.content.compact {
		padding: 0em;
	}
	div.ai {
		align-items: center;
		padding-right: 0.2em;
	}
	div.content.normal {
		padding: 0.2em;
		border-radius: 2px;
	}
	div.content {
		flex-direction: column;
	}
	div.content.loading {
		opacity: 0.5;
	}

	div.row {
		flex-direction: row;
		flex: 1;
		width: 100%;
	}
	div.open {
		border-top: 1px solid rgba(100, 255, 255, 0.3);
		flex-direction: row;
		flex: 1;
		cursor: pointer;
	}
	div.open:hover {
		background-color: rgba(100, 255, 255, 0.3);
	}

	div.expand {
		cursor: pointer;
		flex: 1;
		min-height: 2em;
		border-radius: 2px;
		transition: all 0.3s ease;
	}
	div.active {
		background-color: rgba(100, 255, 255, 0.3);
	}
	div.expand:hover {
		background-color: rgba(100, 255, 255, 0.3);
	}
	div.feature-name {
		flex: 1;
		/* max-width: 12em; */
		padding-right: 0.5em;
	}
	div.segmentationID {
		font-size: x-small;
		flex: 0;
	}
	div.feature-name,
	div.segmentationID,
	div.segmentationType {
		align-items: center;
	}
	div.loading {
		font-size: 0.9em;
		opacity: 0.8;
	}
</style>
