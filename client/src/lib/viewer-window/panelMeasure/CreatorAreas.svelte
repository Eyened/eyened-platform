<script lang="ts">
	import type { Creator } from '$lib/datamodel/creator.svelte';
	import SegmentationArea from './SegmentationArea.svelte';
	import type { Segmentation } from '$lib/datamodel/segmentation.svelte';

	interface Props {
		creator: Creator;
		rows: [Segmentation, number, number | undefined][];
	}
	let { creator, rows }: Props = $props();

	let collapse = $state(true);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<h3 onclick={() => (collapse = !collapse)}>
	{collapse ? '▶' : '▼'}
	{creator.name}
</h3>
<ul class:collapse>
	{#each rows as [annotation, scanNr, area]}
		<SegmentationArea {annotation} {scanNr} {area} />
	{/each}
</ul>

<style>
	ul {
		list-style: none;
		padding-left: 0;
	}

	h3 {
		cursor: pointer;
		margin: 0;
		font-size: small;
        font-weight: normal;
	}
    h3:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }
	ul.collapse {
		display: none;
	}
</style>
