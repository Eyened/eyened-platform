<script lang="ts">
	import InstanceComponent from './InstanceComponent.svelte';
	import { getContext } from 'svelte';

	import type { BrowserContext } from './browserContext.svelte';
	import { page } from '$app/state';
	import { data } from '$lib/datamodel/model';

	const browserContext = getContext<BrowserContext>('browserContext');
	const { instances } = data;

	function clear() {
		browserContext.selection = [];
	}

	function openSelectionTab() {
		const instances = browserContext.selection.join(',');
		let suffix_string = `?instances=${instances}`;
        
		const creatorid = page.url.searchParams.get('creatorid');
		if (creatorid) {
			suffix_string += `&creatorid=${creatorid}`;
		}

		const url = `${window.location.origin}/view${suffix_string}`;
		window.open(url, '_blank')?.focus();
	}
</script>

<div>
	<div class="button-container">
		<div>
			{browserContext.selection.length}
			{browserContext.selection.length != 1 ? 'images' : 'image'} selected
		</div>
		<button disabled={browserContext.selection.length === 0} onclick={openSelectionTab}>
			Open selected images
		</button>
		<button disabled={browserContext.selection.length === 0} onclick={clear}>
			Clear selection
		</button>
	</div>
	<div>
		{#each browserContext.selection as instanceId (instanceId)}
			<InstanceComponent instance={instances.get(instanceId)!} />
		{/each}
	</div>
</div>

<style>
	div {
		display: flex;
		background-color: black;
		color: white;
	}
	div.button-container {
		flex-direction: column;
		padding: 0.5em;
	}
	button {
		padding: 0.5em;
	}
</style>
