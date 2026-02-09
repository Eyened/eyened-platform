<script lang="ts">
	import InstanceInfo from "./InstanceInfo.svelte";
	import { fetchInstance } from "$lib/data/api";
	import { instances } from "$lib/data/stores.svelte";

	interface Props {
		instanceId: string;
	}
	let { instanceId }: Props = $props();

	const loading = fetchInstance(instanceId);
	
	// Check if instance is in store (reactive)
	const instance = $derived(instances.get(instanceId));
</script>

{#await loading}
	<div class="w-[80vw] h-[80vh] flex items-center justify-center">
		<div class="text-sm text-gray-500">Loading…</div>
	</div>
{:then}
	{#if instance}
		<InstanceInfo {instanceId} />
	{:else}
		<div class="w-[80vw] h-[80vh] flex items-center justify-center">
			<div class="text-sm text-red-600">Instance not found</div>
		</div>
	{/if}
{:catch error}
	<div class="w-[80vw] h-[80vh] flex items-center justify-center">
		<div class="text-sm text-red-600">{error}</div>
	</div>
{/await}
