<script lang="ts">
	import { getContext } from 'svelte';
	import TopViewer from './TopViewer.svelte';
	import type { ViewerWindowContext } from './viewerWindowContext.svelte';
	import Spinner from '$lib/utils/Spinner.svelte';

	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');
	const { instanceIds } = viewerWindowContext;
</script>

{#if $instanceIds.length == 0}
	<div class="empty">Enter instance IDs in url</div>
{:else}
	{#each $instanceIds as instanceId}
		{#await viewerWindowContext.getImages(instanceId)}
			<div class="itemLoading">
				<div>Loading {instanceId}</div>
				<Spinner />
			</div>
		{:then images}
			{#each images as image}
				<TopViewer {image} />
			{/each}
		{/await}
	{/each}
{/if}

<style>
	div.empty {
		padding: 2em;
		flex: 1;
		background-color: white;
		color: black;
		z-index: 2;
	}
	div.itemLoading {
		display: flex;
		flex: 1;
		flex-direction: column;
		align-items: center;
		flex-direction: column;
		background-color: black;
		border: 1px solid black;
		border-right: 1px solid gray;
		color: white;
		padding-top: 2em;
		z-index: 2;
	}
</style>
