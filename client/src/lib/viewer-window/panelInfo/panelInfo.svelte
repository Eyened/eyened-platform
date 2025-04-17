<script lang="ts">
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext } from 'svelte';
	import { imageInfoExtensions } from '$lib/extensions';

	const viewerContext = getContext<ViewerContext>('viewerContext');
	const { image } = viewerContext;
	const { instance } = image;

	const instanceProperties = {
		'Patient ID': instance.patient.identifier,
		Date: instance.study.date.toISOString().slice(0, 10),
		Laterality: instance.laterality,
		Camera: instance.device?.model,
		'Scan mode': instance.scan?.mode,
		'ETDRS Field': instance.etdrsField
	};
</script>

<div id="main">
	<table>
		<tbody>
			{#each Object.entries(instanceProperties) as [name, value]}
				<tr>
					<td>{name}</td>
					<td>{value}</td>
				</tr>
			{/each}
		</tbody>
	</table>
	{#each imageInfoExtensions as extension}
		<extension.component {instance} {...extension.props} />
	{/each}
</div>

<style>
	div {
		flex: 1;
		display: flex;
	}
	div#main {
		flex-direction: column;
		padding: 0.5em;
	}
	table {
		border-collapse: collapse;
	}
	td {
		padding: 0.1em;
	}
	tr:nth-child(even) {
		background-color: rgba(255, 255, 255, 0.1);
	}
	tr:nth-child(odd) {
		background-color: rgba(255, 255, 255, 0.05);
	}
	tr:hover {
		background-color: rgba(255, 255, 255, 0.2);
	}
</style>
