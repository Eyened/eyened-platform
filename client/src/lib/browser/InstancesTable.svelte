<script lang="ts">
	import type { Instance } from '$lib/datamodel/instance.svelte';
	import InstanceComponent from './InstanceComponent.svelte';

	interface Props {
		instances: Instance[];
	}

	let { instances }: Props = $props();
</script>

<div>
	<div class="container">
		{#each instances as instance}
			<InstanceComponent {instance} showPatientInfo={true} />
		{/each}
	</div>
</div>

<style>
	div.container {
		display: flex;
		flex-wrap: wrap;
	}
</style>
