<script lang="ts">
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext } from 'svelte';
	import FeatureColorPicker from './FeatureColorPicker.svelte';
	import { Hide, PanelIcon, Show, Trash } from '../icons/icons';
	import type { Branch, DialogueType } from '$lib/types';
	import SegmentationTools from './SegmentationTools.svelte';
	import type { AnnotationData } from '$lib/datamodel/annotationData';
	import type { Writable } from 'svelte/store';

	import type { Annotation } from '$lib/datamodel/annotation';
	import { SegmentationOverlay } from '$lib/viewer/overlays/SegmentationOverlay.svelte';
	import { SegmentationContext } from './segmentationContext.svelte';
	import type { GlobalContext } from '$lib/data-loading/globalContext.svelte';

	interface Props {
		branch: Branch;
		annotationData: AnnotationData;
		maskAnnotation: Annotation;
	}

	let { branch, annotationData, maskAnnotation }: Props = $props();
	const { annotation } = annotationData;
	const globalContext = getContext<GlobalContext>('globalContext');
	const viewerContext = getContext<ViewerContext>('viewerContext');
	const segmentationContext = getContext<SegmentationContext>('segmentationContext');
	const segmentationOverlay = getContext<SegmentationOverlay>('segmentationOverlay');
	const segmentationController = viewerContext.image.segmentationController;

	// TODO: find a cleaner solution?
	const isEditable = globalContext?.canEdit(annotation);

	const segmentationItem = segmentationController.getMaskedSegmentation(
		annotation,
		maskAnnotation,
		branch
	);
	const segmentation = segmentationItem.segmentation;
	// by default show masked segmentation
	segmentationOverlay.applyMasking.add(segmentation);

	let active: boolean = $derived(segmentationContext.activeSegmentation == segmentation);

	const dialogue = getContext<Writable<DialogueType>>('dialogue');

	function deleteBranch() {
		const hide = () => dialogue.set(undefined);
		const reject = hide;
		const resolve = async () => {
			const value = annotationData.value.value;
			value.branches = value.branches.filter((b: Branch) => b != branch);
			segmentationController.removeSegmentation(segmentation);
			dialogue.set(`Updating data for ${annotation.id}...`);
			await annotationData.value.setValue(value);
			dialogue.set(undefined);
		};
		const d = {
			query: `Remove branch ${branch.id}?`,
			approve: 'Delete',
			decline: 'Cancel',
			resolve,
			reject
		};
		dialogue.set(d);
	}
	function toggleActive() {
		segmentationContext.toggleActive(segmentation);
	}
	function toggleShow() {
		segmentationContext.toggleShow(segmentation);
	}
	function toggleApplyMask() {
		segmentationOverlay.toggleMasking(segmentation);
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main" class:active>
	<div class="row toggle" onclick={toggleActive}>
		<FeatureColorPicker {segmentation} />

		<div>
			{#if segmentationContext.hideSegmentations.has(segmentation)}
				<PanelIcon onclick={toggleShow} tooltip="Hide"><Hide /></PanelIcon>
			{:else}
				<PanelIcon onclick={toggleShow} tooltip="Show"><Show /></PanelIcon>
			{/if}
		</div>

		<div class="feature-name">{branch.id}</div>

		{#if isEditable}
			<PanelIcon onclick={deleteBranch} tooltip="Delete branch">
				<Trash />
			</PanelIcon>
		{/if}
	</div>
	{#if active}
		<div class="row">
			{#if segmentationOverlay.applyMasking.has(segmentation)}
				<PanelIcon onclick={toggleApplyMask} tooltip="Show"><Hide /></PanelIcon>
			{:else}
				<PanelIcon onclick={toggleApplyMask} tooltip="Hide"><Show /></PanelIcon>
			{/if}
			Apply masking
		</div>
		<div class="row">
			{#if isEditable}
				<SegmentationTools {segmentationItem} />
			{/if}
		</div>
	{/if}
</div>

<style>
	div {
		display: flex;
		align-items: center;
	}
	div.main {
		flex-direction: column;
		border-left: 2px solid rgba(255, 255, 255, 0);
		border-radius: 2px;
		flex: 1;
		width: 100%;
	}
	div.row.toggle:hover {
		background-color: rgba(200, 255, 255, 0.3);
	}
	div.main.active {
		background-color: rgba(200, 255, 255, 0.3);
		border-left: 2px solid white;
	}
	div.row {
		flex: 1;
		width: 100%;
		align-items: center;
	}
	div.feature-name {
		flex: 1;
		margin-left: 0.2em;
	}
</style>
