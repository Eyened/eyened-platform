<script lang="ts">
	import { getContext } from 'svelte';
	import type { BrowserContext } from './browserContext.svelte';
	import InstanceComponent from './InstanceComponent.svelte';
	import PaginatedResults from './PaginatedResults.svelte';
	import StudyBlock from './StudyBlock.svelte';

	const browserContext = getContext<BrowserContext>('browserContext');

	// export let renderMode: 'studies' | 'instances' = 'studies';
	let { mode = 'full' }: { mode?: 'full' | 'overlay' } = $props();

	function onPageChange(pageNum: number) {
		browserContext.page = pageNum;
		// Re-run search with whichever mode is active
		browserContext.search();
	}

</script>

{#if browserContext.queryMode == "instances"}
	{#if browserContext.displayMode === 'instance'}
		{#if browserContext.orderedInstanceIds.length > 0}
			<PaginatedResults onChange={onPageChange}>
				<div class="grid gap-2 grid-cols-[repeat(auto-fill,minmax(8em,1fr))]">
					{#each browserContext.orderedInstanceIds as id (id)}
						<InstanceComponent instance={browserContext.InstanceRepo.store[id]!} />
					{/each}
				</div>
			</PaginatedResults>
		{:else}
			<div class="flex flex-col flex-1">No results</div>
		{/if}
	{:else}
		{#if browserContext.orderedStudyIds.length > 0}
			<PaginatedResults onChange={onPageChange}>
				{#each browserContext.orderedStudyIds as sid (sid)}
					<StudyBlock study={browserContext.StudiesRepo.object(sid)} {mode} />
				{/each}
			</PaginatedResults>
		{:else}
			<div class="flex flex-col flex-1">No results</div>
		{/if}
	{/if}
{:else if browserContext.queryMode == "studies"}
	{#if browserContext.orderedStudyIds.length > 0}
		<PaginatedResults onChange={onPageChange}>
			{#each browserContext.orderedStudyIds as sid (sid)}		
				<StudyBlock study={browserContext.StudiesRepo.object(sid)} {mode} />
			{/each}
		</PaginatedResults>
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