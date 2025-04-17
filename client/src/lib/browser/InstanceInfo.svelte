<script lang="ts">
	import { getThumbUrl } from '$lib/data-loading/utils';
	import type { Instance } from '$lib/datamodel/instance';
	import InstanceSegmentationTable from './InstanceSegmentationTable.svelte';

	interface Props {
		instance: Instance;
	}
	let { instance }: Props = $props();
</script>

<div id="main">
	<div class="content">
		<div class="img-preview">
			<img src={getThumbUrl(instance)} alt="preview" />
		</div>
		<table>
			<thead>
				<tr>
					<th>Property</th>
					<th>Value</th>
				</tr>
			</thead>
			<tbody>
				{#each Object.entries(instance) as [key, value]}
					<tr>
						<td>{key}</td>
						<!-- Not sure if this is the way to go, but it's a quick fix -->
						{#if key === 'device'}
							<td>{value.model}</td>
						{:else if key === 'scan'}
							{#if value}
								<td>{value.mode}</td>
							{:else}
								<td>N/A</td>
							{/if}
						{:else if ['series', 'study', 'patient', 'project'].includes(key) }
							<td>{value.id}</td>
						{:else}
							<td>{value}</td>
						{/if}
					</tr>
				{/each}
			</tbody>
		</table>
		<InstanceSegmentationTable {instance} />
	</div>
</div>

<style>
	div#main {
		overflow: auto;
	}
	div.content {
		display: flex;
		flex-direction: column;
		flex: 1;
		padding: 1em;
	}

	table {
		font-size: small;
		table-layout: fixed;
		border-collapse: collapse;
		color: gray;
	}
	th {
		color: black;
		font-weight: bold;
	}
	tr:nth-child(even) {
		background-color: rgb(230, 230, 230);
	}
	tr:nth-child(odd) {
		background-color: rgb(245, 245, 245);
	}
	tr:hover {
		background-color: white;
	}
	td {
		word-wrap: break-all;
		padding: 0.1em;
		border-top: 1px solid gray;
	}
</style>
