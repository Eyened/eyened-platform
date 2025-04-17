<script lang="ts">
	import type { Study } from '$lib/datamodel/study';
	import SeriesComponent from './SeriesComponent.svelte';

	interface Props {
		study: Study;
		laterality: 'L' | 'R';
	}

	let { study, laterality }: Props = $props();

	const eye = { L: 'OS', R: 'OD' }[laterality];
	const filtered = study.instances.filter((instance) => instance.laterality == laterality);
	const bySeries = filtered.collectSet((instance) => instance.series);
</script>

<div class="outer">
	<h3>{eye}</h3>
	<div class="series-container">
		{#each [...$bySeries].sort((a, b) => a.id - b.id) as series (series.id)}
			<SeriesComponent {series} {laterality}/>
		{/each}
	</div>
</div>

<style>
	div {
		display: flex;
	}
	h3 {
		margin: 0;
		font-size: normal;
	}
	.outer {
		flex: 1;
		flex-direction: column;
		padding: 0.5em;
	}
	.series-container {
		flex-wrap: wrap;
		align-content: flex-start;
		flex: 1;
		flex-direction: row;
	}
</style>
