<script lang="ts">
	import type { DialogueType } from '$lib/types';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext } from 'svelte';
	import {
		Branch,
		Duplicate,
		Hide,
		ImportSegmentation,
		PanelIcon,
		Show,
		Trash
	} from '../icons/icons';
	import FeatureColorPicker from './FeatureColorPicker.svelte';
	import SegmentationTools from './SegmentationTools.svelte';
	import ImportSegmentationSelector from './ImportSegmentationSelector.svelte';
	import BscanLinks from './BscanLinks.svelte';
	import ConnectedComponents from '../icons/ConnectedComponents.svelte';
	import { type Annotation } from '$lib/datamodel/annotation';
	import { SegmentationOverlay } from '$lib/viewer/overlays/SegmentationOverlay.svelte';
	import { createMaskedAnnotation, deleteAnnotation } from './segmentationUtils';
	import { data } from '$lib/datamodel/model';
	import type { Segmentation } from '$lib/webgl/SegmentationController';
	import { BinarySegmentation } from '$lib/webgl/binarySegmentation.svelte';
	import { ProbabilitySegmentation } from '$lib/webgl/probabilitySegmentation.svelte';
	import type { Writable } from 'svelte/store';
	import { SegmentationContext } from './segmentationContext.svelte';
	import ThresholdSlider from './ThresholdSlider.svelte';
	import type { GlobalContext } from '$lib/data-loading/globalContext.svelte';

	interface Props {
		annotation: Annotation;
	}
	let { annotation }: Props = $props();
	const { annotationDatas, feature, annotationType } = annotation;
	const globalContext = getContext<GlobalContext>('globalContext');

	const viewerContext = getContext<ViewerContext>('viewerContext');

	const image = viewerContext.image;
	const segmentationController = image.segmentationController;
	const segmentationContext = getContext<SegmentationContext>('segmentationContext');

	const segmentationItem = segmentationController.getSegmentationItem(annotation);
	// const segmentationItem = new SegmentationItem(image, annotation, segmentation);
	const segmentation = segmentationItem.segmentation;

	const isEditable = globalContext?.canEdit(annotation);
	const isVessels = feature.name == 'Vessels';

	let active = $derived(segmentationContext.activeSegmentation == segmentation);

	function activate() {
		if (segmentationContext.activeSegmentation == segmentation) {
			segmentationContext.activeSegmentation = undefined;
		} else {
			segmentationContext.activeSegmentation = segmentation;
		}
	}

	function toggleShow() {
		if (segmentationContext.hideSegmentations.has(segmentation)) {
			segmentationContext.hideSegmentations.delete(segmentation);
		} else {
			segmentationContext.hideSegmentations.add(segmentation);
		}
	}

	const dialogue = getContext<Writable<DialogueType>>('dialogue');

	async function removeAnnotation() {
		deleteAnnotation(dialogue, annotation, () =>
			image.segmentationController.removeAnnotation(annotation)
		);
		segmentationContext.activeSegmentation = undefined;
	}

	async function duplicate(type?: string) {
		dialogue.set(`duplicating annotation ${annotation.id}...`);

		let interpretation = annotation.annotationType.interpretation;
		let name = annotation.annotationType.name;
		if (interpretation == 'Binary mask') {
			// Interpretation 'binary mask' (model output) will be changed to 'R/G'
			interpretation = 'R/G mask';
		}
		if (name == 'Segmentation OCT Volume') {
			// Type 'OCT Volume' (model output) will be changed to 'OCT B-scan'
			name = 'Segmentation OCT B-scan';
		}
		if (type == 'R/G mask') {
			// Used to create a new annotation with interpretation 'R/G mask' instead of 'Probability'
			interpretation = 'R/G mask';
		}

		const annotationType = data.annotationTypes.find(
			(a) => a.name == name && a.interpretation == interpretation
		);
		if (!annotationType) {
			throw new Error('Annotation type not found');
		}

		const creator = globalContext.creator;
		const item = { ...annotation, annotationType, creator };
		const newAnnotation = await data.annotations.create(item);
		const newSegmentationItem = segmentationController.getSegmentationItem(newAnnotation);

		const scanNr = viewerContext.index;
		newSegmentationItem.importOther(scanNr, segmentation);

		dialogue.set(undefined);
	}

	function createMasked() {
		createMaskedAnnotation(dialogue, annotation, globalContext.creator, viewerContext.index);
	}

	async function importFromOther() {
		const hide = () => dialogue.set(undefined);
		const reject = hide;
		const resolve = (other: Segmentation) => {
			const scanNr = viewerContext.index;
			segmentation.importOther(scanNr, other);
			segmentationItem.checkpoint(scanNr);
			hide();
		};
		const d = {
			query: ImportSegmentationSelector,
			props: {
				segmentation,
				availableSegmentations: segmentationController.allSegmentations
			},
			approve: 'Import',
			decline: 'Cancel',
			resolve,
			reject
		};

		dialogue.set(d);
	}

	let notOnBscan = $derived.by(() => {
		if (annotationType.name == 'Segmentation OCT Volume') {
			return false;
		} else {
			for (const a of $annotationDatas) {
				if (a.scanNr == viewerContext.index) {
					return false;
				}
			}
			return true;
		}
	});

	const segmentationOverlay = getContext<SegmentationOverlay>('segmentationOverlay');
	const connectedComponentsOverlay = segmentationOverlay.connectedComponentsOverlay;
	let connectedComponentsActive = $derived(connectedComponentsOverlay.mode.has(segmentation));
	function toggleConnectedComponents() {
		connectedComponentsOverlay.toggleMode(segmentation as BinarySegmentation);
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="main" class:active class:notOnBscan>
	{#if active && image.is3D && annotationType.name != 'Segmentation OCT Volume' && segmentation}
		<BscanLinks {annotation} {segmentation} />
	{/if}
	<div class="row">
		{#if (segmentation && segmentation instanceof BinarySegmentation) || segmentation instanceof ProbabilitySegmentation}
			<FeatureColorPicker {segmentation} />
		{/if}

		<div>
			{#if segmentationContext.hideSegmentations.has(segmentation)}
				<PanelIcon onclick={toggleShow} tooltip="Show"><Hide /></PanelIcon>
			{:else}
				<PanelIcon onclick={toggleShow} tooltip="Hide"><Show /></PanelIcon>
			{/if}
			{#if isVessels}
				<PanelIcon
					active={connectedComponentsActive}
					onclick={toggleConnectedComponents}
					tooltip={(connectedComponentsActive ? 'Hide' : 'Show') + ' connected components'}
				>
					<ConnectedComponents />
				</PanelIcon>
			{/if}
		</div>

		<div class="expand" onclick={activate}>
			<div class="feature-name">{feature.name}</div>
			<div class="annotationID">
				{annotation.id}
			</div>
		</div>

		{#if isEditable}
			<PanelIcon onclick={removeAnnotation} tooltip="Delete">
				<Trash />
			</PanelIcon>
		{/if}
	</div>

	{#if active}
		{#if segmentation instanceof ProbabilitySegmentation}
			<div class="row">
				<ThresholdSlider {segmentation} />
			</div>
		{/if}
		<div class="row">
			<PanelIcon onclick={() => duplicate('R/G mask')} tooltip="Duplicate">
				<Duplicate />
			</PanelIcon>

			{#if segmentation instanceof ProbabilitySegmentation}
				<PanelIcon onclick={() => duplicate('Probability')} tooltip="Duplicate Probability">
					<Duplicate />
				</PanelIcon>
			{/if}
			{#if isEditable}
				<PanelIcon onclick={importFromOther} tooltip="Import from other">
					<ImportSegmentation />
				</PanelIcon>
			{/if}
			{#if isVessels}
				<PanelIcon onclick={createMasked} tooltip="Label branches">
					<Branch />
				</PanelIcon>
			{/if}
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
	div.notOnBscan {
		opacity: 0.2;
	}
	div.main {
		flex-direction: column;
		border-left: 2px solid rgba(255, 255, 255, 0);
	}
	div.main.active {
		border-radius: 2px;
		background-color: rgba(100, 255, 255, 0.3);
		border-left: 2px solid white;
	}
	div.row {
		flex-direction: row;
		flex: 1;
		width: 100%;
	}
	div.expand {
		cursor: pointer;
		flex: 1;
		min-height: 2em;
		border-radius: 2px;
		transition: all 0.3s ease;
	}
	div.expand:hover {
		background-color: rgba(100, 255, 255, 0.3);
	}
	div.feature-name {
		flex: 1;
		/* max-width: 12em; */
		padding-right: 0.5em;
	}
	div.annotationID {
		font-size: x-small;
		align-items: end;
		flex: 0;
	}
</style>
