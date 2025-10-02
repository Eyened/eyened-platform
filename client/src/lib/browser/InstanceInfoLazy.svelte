<script lang="ts">
	import { InstanceObject } from '$lib/data/objects.svelte';
	import type { InstanceGET } from '../../types/openapi_types';
	import InstanceInfo from './InstanceInfo.svelte';

	interface Props { 
		instanceId: number; 
	}
	let { instanceId }: Props = $props();

	let loading = $state(true);
	let error: string | null = $state(null);
	let instanceFull: InstanceGET | null = $state(null);

	$effect(() => {
		const loadInstance = async () => {
			loading = true;
			error = null;
			instanceFull = null;
			try {
				const obj = await InstanceObject.fromId<InstanceGET>(instanceId);
				instanceFull = obj.$;
			} catch (e) {
				error = (e as Error)?.message ?? 'Failed to load instance';
			} finally {
				loading = false;
			}
		};
		loadInstance();
	});
</script>

{#if loading}
	<div class="w-[80vw] h-[80vh] flex items-center justify-center">
		<div class="text-sm text-gray-500">Loading…</div>
	</div>
{:else if error}
	<div class="w-[80vw] h-[80vh] flex items-center justify-center">
		<div class="text-sm text-red-600">{error}</div>
	</div>
{:else if instanceFull}
	<InstanceInfo instance={instanceFull}/>
{/if}
