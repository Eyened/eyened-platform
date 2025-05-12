<script lang="ts">
	import type { Series } from '$lib/datamodel/series';
	import InstanceComponent from './InstanceComponent.svelte';

	interface Props {
		series: Series;
		laterality: 'L' | 'R';
		showSegmentationInfo?: boolean;
	}

	let { series, laterality, showSegmentationInfo = true }: Props = $props();

	const { instances } = series;

	const filtered = instances
		.filter((instance) => instance.laterality == laterality)
		.sort((a, b) => a.id - b.id);
</script>

{#if $filtered.length}
	<div class="series">
		<div class="items">
			{#each $filtered as instance}
				<InstanceComponent {instance} {showSegmentationInfo} />
			{/each}
		</div>
	</div>
{/if}

<style>
	div {
		display: flex;
	}
	.series {
		flex-direction: column;
		background-color: var(--browser-background);
		border: 1px solid var(--browser-border);
		border-radius: 2px;
		flex: 0 1 auto;
		margin: 0.1em;
	}
	.items {
		display: flex;
		flex: 1;
		flex-direction: row;
		flex-wrap: wrap;
		gap: 0.3em;
	}
</style>
