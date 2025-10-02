<script lang="ts">
	import type { Instance } from '$lib/datamodel/instance.svelte';

	interface Props {
		instance: Instance;
	}

	let { instance }: Props = $props();
	const segmentations = instance.segmentations;
</script>

<div id="main">
	{#if $segmentations.length}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div>
			<h4>Segmentations:</h4>
			<table class="bg-white text-sm">
				<thead>
					<tr>
						<th class="px-[0.2em] text-left whitespace-nowrap overflow-hidden text-ellipsis">ID</th>
						<th class="px-[0.2em] text-left whitespace-nowrap overflow-hidden text-ellipsis">Creator</th>
						<th class="px-[0.2em] text-left whitespace-nowrap overflow-hidden text-ellipsis">Feature</th>
					</tr>
				</thead>
				<tbody>
					{#each $segmentations as segmentation}
						<tr>
							<td class="px-[0.2em] text-left whitespace-nowrap overflow-hidden text-ellipsis">{segmentation.id}</td>
							<td class="px-[0.2em] text-left whitespace-nowrap overflow-hidden text-ellipsis">{segmentation.creator.name}</td>
							<td class="px-[0.2em] text-left whitespace-nowrap overflow-hidden text-ellipsis">{segmentation.feature.name}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<style>

</style>
