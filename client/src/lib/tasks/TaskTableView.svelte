<script lang="ts">
	import { browser } from '$app/environment';
	import { data } from '$lib/datamodel/model';
	import type { Task } from '$lib/datamodel/task';
	import type { TaskState } from '$lib/datamodel/taskState';
	import { get_url_params } from '$lib/utils';
	import SubTaskRow from './SubTaskRow.svelte';
	import { get } from 'svelte/store';

	interface Props {
		task: Task;
	}

	let { task }: Props = $props();

	const content = data.subTasks.filter((subTask) => subTask.task === task);

	const states = data.taskStates;

	let filterState: TaskState | undefined = $state(undefined);
	let selectedContent = $derived.by(() => {
		if (filterState) {
			// Note: does not react to changes in subTask.taskState
			return content.filter((subTask) => get(subTask.taskState) === filterState);
		} else {
			return content;
		}
	});

	let selectionStart = $state(0);
	let selectionSize = 100;

	function next() {
		selectionStart = selectionStart + selectionSize;
	}

	function previous() {
		selectionStart = selectionStart - selectionSize;
	}

	let admin = false;
	if (browser) {
		const params = get_url_params();
		admin = Boolean(params.admin);
	}
</script>

Viewing sets {selectionStart + 1} to {Math.min(
	selectionStart + selectionSize,
	$selectedContent.length
)} of {$selectedContent.length}.
<nav>
	{#if selectionStart > 0}
		<button onclick={() => previous()}>Previous</button>
	{/if}

	{#if selectionStart + selectionSize < $selectedContent.length}
		<button onclick={() => next()}>Next</button>
	{/if}
</nav>
<div class="sample">
	<table>
		<thead>
			<tr>
				<th>ID</th>
				<th>
					State
					<select bind:value={filterState}>
						<option value={undefined}>[all]</option>
						{#each $states as state}
							<option value={state}>{state.name}</option>
						{/each}
					</select>
				</th>
				<th></th>
				<th>Images</th>
			</tr>
		</thead>
		<tbody>
			{#each $selectedContent.slice(selectionStart, Math.min(selectionStart + selectionSize, $selectedContent.length)) as subTask, i (subTask.id)}
				<SubTaskRow i={$content.indexOf(subTask)} {subTask} />
			{/each}
		</tbody>
	</table>
</div>
<nav>
	{#if selectionStart > 0}
		<button onclick={() => previous()}>Previous</button>
	{/if}

	{#if selectionStart + selectionSize - 1 < $selectedContent.length}
		<button onclick={() => next()}>Next</button>
	{/if}
</nav>

<style>
	nav {
		display: flex;
		margin-top: 1em;
		margin-bottom: 1em;
	}
	.sample {
		border: 0px;
	}
	table {
		border-collapse: collapse;
		width: 100%;
		border: 1px solid black;
	}
	th {
		padding: 0.8em;
		border: 1px solid rgba(0, 0, 0, 0.1);
	}

	thead {
		background-color: black;
		color: white;
	}


</style>
