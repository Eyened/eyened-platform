<script lang="ts">
	import { getContext } from 'svelte';
	import StudyBlock from './StudyBlock.svelte';
	import type { BrowserContext } from './browserContext.svelte';

    const {StudiesRepo, InstanceRepo, queryMode} = getContext<BrowserContext>('browserContext');

	// export let renderMode: 'studies' | 'instances' = 'studies';
	let { mode = 'full' }: { mode?: 'full' | 'overlay' } = $props();


</script>

{#if queryMode == "instances"}
	{#if InstanceRepo.all.length > 0}
		{'sdfsdf'}
	{/if}
{:else if queryMode == "studies"}
	{#if StudiesRepo.all.length > 0}
		{#each StudiesRepo.all.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()) as study (study)}
			<StudyBlock {study} {mode} />
		{/each}
	{:else}
		<div class="flex flex-col flex-1">No results</div>
	{/if}
{:else}
    <div class="flex flex-col flex-1">No studies found</div>
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
