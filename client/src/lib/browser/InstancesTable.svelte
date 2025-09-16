<script lang="ts">
	import type { Instance } from '$lib/datamodel/instance.svelte';
	import InstanceComponent from './InstanceComponent.svelte';

	interface Props {
		instances: Instance[];
	}

	let { instances }: Props = $props();
</script>

<div>
	<div class="container flex flex-wrap">
		{#each instances as instance}
			<InstanceComponent {instance} showPatientInfo={true} />
		{/each}
	</div>
</div>

<style>

</style>
