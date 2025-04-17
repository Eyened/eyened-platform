<script lang="ts">
	import SegmentationItem from './SegmentationItem.svelte';
	import type { Annotation } from '$lib/datamodel/annotation';
	import SegmentationItemMaskedInit from './SegmentationItemMaskedInit.svelte';
	import SegmentationItemLayers from '../panelLayers/SegmentationItemLayers.svelte';
	
	interface Props {
		annotation: Annotation;
	}

	let { annotation }: Props = $props();
	const interpretation = annotation.annotationType.interpretation;

	const isMasked = annotation.annotationType.name == 'Segmentation 2D masked';
	const isMacularLayers = annotation.feature.name == 'Macular layers';
	const isBinary =
		!isMacularLayers && !isMasked && ['R/G mask', 'Binary mask'].includes(interpretation);
	const isProbability = interpretation == 'Probability';
	let isLayerNumbers = $state(interpretation == 'Label numbers');
	const isLayerBits = interpretation == 'Layer bits';

	// TODO: fix annotation type in database
	if (isMacularLayers && interpretation == 'R/G mask') {
		isLayerNumbers = true;
	}

</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="main">
	{#if isMasked}	
		<SegmentationItemMaskedInit {annotation} />
	{:else if isBinary}
		<SegmentationItem {annotation} />
	{:else if isProbability}
		<SegmentationItem {annotation} />
	{:else if isLayerNumbers || isLayerBits}
		<SegmentationItemLayers {annotation} />
	{/if}
</div>

<style>
	div {
		display: flex;
	}
	div.main {
		position: relative;
		flex-direction: column;
		background-color: rgba(255, 255, 255, 0.1);
		margin: 0.2em;
		/* margin-bottom: 1px; */
		/* border: 1px solid rgba(255, 255, 255, 0.1); */
		border-left: 1px solid rgba(255, 255, 255, 0.1);

		border-radius: 4px;
	}
	div.main:hover {
		background-color: rgba(255, 255, 255, 0.2);
	}
	
</style>
