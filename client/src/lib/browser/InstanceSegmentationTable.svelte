<script lang="ts">
	import type { Instance } from '$lib/datamodel/instance';

	interface Props {
		instance: Instance;
	}

	let { instance }: Props = $props();
	const segmentations = instance.annotations.filter((a) =>
		a.annotationType.name.includes('Segmentation')
	);
</script>

<div id="main">
	{#if $segmentations.length}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div>
			<h4>Segmentations:</h4>
			<table>
				<thead>
					<tr>
						<th>ID</th>
						<th>Creator</th>
						<th>Feature</th>
					</tr>
				</thead>
				<tbody>
					{#each $segmentations as segmentation}
						<tr>
							<td>{segmentation.id}</td>
							<td>{segmentation.creator.name}</td>
							<td>{segmentation.feature.name}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<style>
	table {
		background-color: white;

		font-size: small;
	}
	td,
	th {
		padding: 0.2em;
		text-align: left;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
    
</style>
