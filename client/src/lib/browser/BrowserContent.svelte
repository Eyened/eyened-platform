<script lang="ts">
	import { browserExtensions } from '$lib/extensions';
	import { getContext } from 'svelte';

	import InstancesTable from './InstancesTable.svelte';
	import StudyBlock from './StudyBlock.svelte';
	import { BrowserContext } from './browserContext.svelte';

	interface Props {
		renderMode?: 'studies' | 'instances';
		mode?: 'full' | 'overlay';
	}

	let { renderMode = 'studies', mode = 'full' }: Props = $props();

	const browserContext = getContext<BrowserContext>('browserContext');
	const { instances } = browserContext;
	const studies = instances.filterlist.collectSet((i) => i.study);
    
	// TODO implement pagination
</script>

{#if renderMode == 'instances'}
	{#if $instances.length}
		<InstancesTable instances={$instances} />
	{:else}
		<div class="no-content">No images found</div>
	{/if}
{:else if $studies.size}
	{#each [...$studies].filter((s) => s).sort((a, b) => b.date - a.date) as study (study)}
		<StudyBlock {study} {mode} />
	{/each}
	{#if mode == 'full'}
		{#each browserExtensions as extension}
			<extension.component {...extension.props} />
		{/each}
	{/if}
{:else}
	<div class="no-content">No studies found</div>
{/if}

<style>
	div.no-content {
		display: flex;
		flex-direction: column;
		flex: 1;
	}
</style>
