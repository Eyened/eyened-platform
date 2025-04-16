<script lang="ts">
	import type { AnnotationData } from '$lib/datamodel/annotationData';
	import type { DialogueType } from '$lib/types';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext } from 'svelte';
	import { Hide, PanelIcon, Show, Trash } from '../icons/icons';
	import SegmentationItemBranch from './SegmentationItemBranch.svelte';
	import { type Writable } from 'svelte/store';
	import { data } from '$lib/datamodel/model';
	import { addBranch, deleteAnnotation } from './segmentationUtils';
	import type { SegmentationContext } from './segmentationContext.svelte';
	import type { GlobalContext } from '$lib/data-loading/globalContext.svelte';

	interface Props {
		maskID: number;
		annotationData: AnnotationData;
	}

	let { maskID, annotationData }: Props = $props();

	const {
		annotation,
		annotation: { feature }
	} = annotationData;

	const globalContext = getContext<GlobalContext>('globalContext');
	const { image } = getContext<ViewerContext>('viewerContext');
	const segmentationContext = getContext<SegmentationContext>('segmentationContext');

	function toggleShow() {
		if (segmentationContext.hideAnnotations.has(annotation)) {
			segmentationContext.hideAnnotations.delete(annotation);
		} else {
			segmentationContext.hideAnnotations.add(annotation);
		}
	}
	// TODO: find a cleaner solution?
	const isEditable = globalContext?.canEdit(annotation);

	let branches = $derived(annotationData.value.value.branches);
	const maskAnnotation = data.annotations.find((a) => a.id === maskID);

	const dialogue = getContext<Writable<DialogueType>>('dialogue');

	async function addNewBranch(vesselType: 'Artery' | 'Vein' | 'Vessel') {
		addBranch(dialogue, annotationData, image, vesselType);
	}

	function removeAnnotation() {
		deleteAnnotation(dialogue, annotation, () =>
			image.segmentationController.removeAnnotation(annotation)
		);
	}
</script>

{#if maskAnnotation}
	<div class="main">
		<div class="title">
			<div>
				{#if segmentationContext.hideAnnotations.has(annotation)}
					<PanelIcon onclick={toggleShow} tooltip="Hide"><Hide /></PanelIcon>
				{:else}
					<PanelIcon onclick={toggleShow} tooltip="Show"><Show /></PanelIcon>
				{/if}
			</div>

			<div class="feature-name">{feature.name} [{maskID}]</div>

			<div class="annotationID">{annotation.id}</div>

			{#if isEditable}
				<PanelIcon onclick={removeAnnotation} tooltip="Delete">
					<Trash />
				</PanelIcon>
			{/if}
		</div>

		<div class="branches">
			{#each branches as branch (branch.id)}
				<SegmentationItemBranch {annotationData} {maskAnnotation} {branch} />
			{/each}
		</div>

		{#if isEditable}
			<div class="add-branch">
				<span>New:</span>
				<PanelIcon onclick={() => addNewBranch('Artery')} tooltip="Add artery" isText={true}>
					Artery
				</PanelIcon>
				<PanelIcon onclick={() => addNewBranch('Vein')} tooltip="Add vein" isText={true}>
					Vein
				</PanelIcon>
				<PanelIcon onclick={() => addNewBranch('Vessel')} tooltip="Add vessel" isText={true}>
					Vessel
				</PanelIcon>
			</div>
		{/if}
	</div>
{:else}
	No annotation found for maskID {maskID}

	{#if isEditable}
		<PanelIcon onclick={removeAnnotation} tooltip="Delete">
			<Trash />
		</PanelIcon>
	{/if}
{/if}

<style>
	div {
		display: flex;
		align-items: center;
	}
	div.main {
		flex-direction: column;
		border-left: 2px solid rgba(255, 255, 255, 0);
		border-radius: 2px;
		align-items: start;
	}
	div.feature-name {
		flex: 1;
	}
	div.branches {
		flex-direction: column;
		flex: 1;
		align-items: start;
	}
	div.title,
	div.branches {
		width: 100%;
	}
	div.annotationID {
		font-size: x-small;
		align-items: end;
	}
</style>
