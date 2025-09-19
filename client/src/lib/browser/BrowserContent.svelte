<script lang="ts">
	import { getContext } from 'svelte';
	import InstanceComponent from './InstanceComponent.svelte';
	import StudyBlock from './StudyBlock.svelte';
	import type { BrowserContext } from './browserContext.svelte';

	const browserContext = getContext<BrowserContext>('browserContext');

	// export let renderMode: 'studies' | 'instances' = 'studies';
	let { mode = 'full' }: { mode?: 'full' | 'overlay' } = $props();

	

</script>

{#if browserContext.queryMode == "instances"}
	{#if browserContext.displayMode === 'instance'}
		{#if browserContext.orderedInstanceIds.length > 0}
			<div class="grid gap-2 grid-cols-[repeat(auto-fill,minmax(8em,1fr))]">
				{#each browserContext.orderedInstanceIds as id (id)}
					<InstanceComponent instance={browserContext.InstanceRepo.object(id)} />
				{/each}
			</div>
		{:else}
			<div class="flex flex-col flex-1">No results</div>
		{/if}
	{:else}
		{#if browserContext.orderedStudyIds.length > 0}
			{#each browserContext.orderedStudyIds as sid (sid)}
				<StudyBlock study={browserContext.StudiesRepo.object(sid)} {mode} />
			{/each}
		{:else}
			<div class="flex flex-col flex-1">No results</div>
		{/if}
	{/if}
{:else if browserContext.queryMode == "studies"}
	{#if browserContext.orderedStudyIds.length > 0}
		{#each browserContext.orderedStudyIds as sid (sid)}
			<StudyBlock study={browserContext.StudiesRepo.object(sid)} {mode} />
		{/each}
	{:else}
		<div class="flex flex-col flex-1">No results</div>
	{/if}
{:else}
    <div class="no-content">No studies found</div>
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

</style>