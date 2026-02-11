<script lang="ts">
	import { deleteSegmentation } from "$lib/data/api";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext } from "svelte";
	import { Hide, PanelIcon, Show, Trash } from "../icons/icons";
	import ThresholdSlider from "./ThresholdSlider.svelte";

	import StringDialogue from "$lib/StringDialogue.svelte";
	import CCPanel from "./CCPanel.svelte";
	import { duplicate } from "./duplicate_utils";
	import DuplicateAnnotationPanel from "./DuplicateAnnotationPanel.svelte";
	import FeatureColorPicker from "./FeatureColorPicker.svelte";
	import ImportPanel from "./ImportPanel.svelte";
	import MultiFeatureSelector from "./MultiFeatureSelector.svelte";
	import ReferenceSegmentationPanel from "./ReferenceSegmentationPanel.svelte";
	import {
		getSegmentationKey,
		type Segmentation,
	} from "./segmentationContext.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";

	const globalContext = getContext<GlobalContext>("globalContext");
	const viewerContext = getContext<ViewerContext>("viewerContext");
	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
	const taskContext = getContext<TaskContext>("taskContext");
	const segmentationContext = mainViewerContext.segmentationContext;

	interface Props {
		segmentation: Segmentation;
	}

	let { segmentation }: Props = $props();

	const feature = segmentation.feature;
	const dataRepresentation = segmentation.data_representation;
	const image = viewerContext.image;

	const visible = $derived(
		segmentationContext.shownSegmentations.has(
			getSegmentationKey(segmentation),
		),
	);

	const segmentationItem =
		segmentationContext.getSegmentationItem(segmentation);

	const segmentationState = $derived(
		segmentationItem.getSegmentationState(viewerContext.index),
	);
	const syncState = $derived(segmentationState?.syncState ?? null);
	const isEditable = globalContext.canEdit(segmentation);
	const isEmptyForCurrentSlice = $derived(
		segmentationItem.isEmptyForSlice(viewerContext.index),
	);
	let collapsed = $state(true);

	async function remove() {
		const resolve = async () => {
			// remove from database on server
			if (segmentation.annotation_type === "grader_segmentation") {
				await deleteSegmentation(segmentation.id);
			}
			if (segmentationContext.segmentationItem == segmentationItem) {
				segmentationContext.segmentationItem = undefined;
			}
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

	function toggleActive() {
		segmentationContext.toggleActive(segmentationItem);
	}

	const active = $derived(
		segmentationContext.segmentationItem == segmentationItem,
	);

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

	function applyDuplicateAI() {
		duplicate(
			globalContext,
			segmentation,
			segmentationItem,
			image,
			viewerContext,
			false,
			"Q",
			segmentationItem.threshold ?? segmentation.threshold ?? 0.5, //original threshold
			0.5, //new threshold
			taskContext,
		);
	}
</script>

<div
	class="content"
	class:loading={segmentationItem.loading}
	class:active
	class:empty-non-editable={!isEditable && isEmptyForCurrentSlice}
	class:empty-editable={isEditable && isEmptyForCurrentSlice}
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

		<button type="button" class="expand" onclick={toggleActive}>
			<div class="feature-name">{feature.name}</div>
			<div class="segmentationID">[{segmentation.id}]</div>
			<div class="segmentationType">[{segmentationType}]</div>
		</button>

		{#if isEditable}
			<PanelIcon onclick={remove} tooltip="Delete" Icon={Trash} />
		{/if}
	</div>

	{#if dataRepresentation == "Probability"}
		{#if active}
			<div class="row">
				<ThresholdSlider {segmentation} {segmentationItem} />
			</div>
		{/if}
	{/if}
	{#if active && segmentation.annotation_type == "model_segmentation"}
		<div class="row">
			<button type="button" class="duplicate-button" onclick={applyDuplicateAI}>
				Duplicate
			</button>
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
		<button type="button" class="open" onclick={() => (collapsed = !collapsed)}>
			<div class="handle">
				{#if collapsed}
					&#9654;
				{:else}
					&#9660;
				{/if}
			</div>
			{#if segmentationState && syncState && isEditable}
				<div
					class="sync-indicator"
					class:synced={syncState === "synced"}
					class:saving={syncState === "saving"}
					class:error={syncState === "error"}
				>
					<div class="traffic-light"></div>
				</div>
			{/if}
		</button>

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
	div.content {
		flex-direction: column;
	}
	div.content.loading {
		opacity: 0.5;
	}

	div.content.empty-non-editable {
		opacity: 0.6;
		pointer-events: none;
	}

	div.content.empty-editable {
		background-color: rgba(100, 255, 255, 0.15);
	}

	div.row {
		flex-direction: row;
		flex: 1;
		width: 100%;
		align-items: center;
	}
	button.open {
		border-top: 1px solid rgba(100, 255, 255, 0.3);
		flex-direction: row;
		flex: 1;
		cursor: pointer;
	}
	button.open:hover {
		background-color: rgba(100, 255, 255, 0.3);
	}

	button.expand {
		cursor: pointer;
		flex: 1;
		min-height: 2em;
		border-radius: 2px;
		transition: all 0.3s ease;
	}
	div.active {
		background-color: rgba(100, 255, 255, 0.3);
	}
	button.expand:hover {
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
	div.feature-name {
		text-align: left;
		font-size: small;
	}
	div.segmentationID,
	div.segmentationType {
		align-items: center;
	}
	div.loading {
		font-size: 0.9em;
		opacity: 0.8;
	}

	button {
		background: transparent;
		border: none;
		color: inherit;
		display: flex;
		align-items: center;
		justify-content: flex-start;
		padding: 0;
	}
	button:focus-visible {
		outline: 2px solid currentColor;
		outline-offset: 2px;
	}
	button.duplicate-button {
		cursor: pointer;
		padding: 0.2em;
		border-radius: 2px;
		border: 1px solid rgba(255, 255, 255, 0.3);
		margin: 0.2em;
		text-wrap-mode: nowrap;
	}
	button.duplicate-button:hover {
		background-color: rgba(255, 255, 255, 0.3);
	}

	div.sync-indicator {
		margin-right: 0.5em;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	div.traffic-light {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background-color: gray;
		transition: background-color 0.2s ease;
	}

	div.handle {
		flex: 1;
        padding-left: 0.5em;
	}

	div.sync-indicator.synced .traffic-light {
		background-color: #22c55e; /* green */
	}

	div.sync-indicator.saving .traffic-light {
		background-color: #f59e0b; /* orange */
	}

	div.sync-indicator.error .traffic-light {
		background-color: #ef4444; /* red */
	}
</style>
