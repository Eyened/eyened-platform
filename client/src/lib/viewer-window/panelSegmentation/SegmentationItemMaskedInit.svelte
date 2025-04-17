<script lang="ts">
	import type { Annotation } from '$lib/datamodel/annotation';
	import SegmentationItemMasked from './SegmentationItemMasked.svelte';

	interface Props {
		annotation: Annotation;
	}

	let { annotation }: Props = $props();
	const { annotationDatas } = annotation;
</script>

{#each $annotationDatas as annotationData (annotationData.id)}
	{#await annotationData.value.load()}
		<p>Loading...{annotation.id} [{annotationData.scanNr}]</p>
	{:then value}
		{#if value?.maskID}
			<SegmentationItemMasked {annotationData} maskID={value.maskID} />
		{/if}
	{/await}
{/each}
