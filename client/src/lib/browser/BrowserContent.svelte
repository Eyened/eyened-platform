<script lang="ts">
	import { getContext } from 'svelte'
	import StudyBlock from './StudyBlock.svelte'
	import type { BrowserContext } from './browserContext.svelte'

    const {StudiesRepo, InstanceRepo} = getContext<BrowserContext>('browserContext');

	// export let renderMode: 'studies' | 'instances' = 'studies';
	export let mode: 'full' | 'overlay' = 'full';

	const optio = {};

	// iterating over the studies in the loaded instances rather than the studies directly
	// because the instances may be capped by the limit and may therefore not be complete
	// TODO: perhaps the limit / page in the query should be interpreted differently?

	
	// const studies = instances.filterlist.collectSet((i) => i.study);
	

	// const optio_list = optio ? Object.entries(optio).map(([tag, values]) => ({ tag, values })) : [];


	// TODO implement pagination
</script>

{#if StudiesRepo.all().length > 0}
	{#each StudiesRepo.all().sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()) as study (study)}
		<StudyBlock {study} {optio} {mode} />
	{/each}
{:else}
	<div class="no-content">No results</div>
{/if}

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<!-- <div class="optio">
	<h3>All optio forms:</h3>
	<ul class="forms">
		{#each optio_list as { tag, values }}
			<li on:click={() => ($selectedOptio = { tag, values })}>
				{tag}
			</li>
		{/each}
	</ul>
</div> -->

<style>
	div.optio {
		display: flex;
		flex-direction: column;
	}
	ul {
		list-style-type: none;
		padding-left: 1em;
		margin-top: 0;
	}
	ul.forms > li:hover {
		background-color: lightgray;
		cursor: pointer;
	}
	div.no-content {
		display: flex;
		flex-direction: column;
		flex: 1;
	}
</style>