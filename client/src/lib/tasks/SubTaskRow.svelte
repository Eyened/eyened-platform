<script lang="ts">
	import { page } from '$app/state';

	import type { SubTask } from '$lib/datamodel/subTask';

	interface Props {
		i: number;
		subTask: SubTask;
	}

	let { i, subTask }: Props = $props();
	const { instanceIds, taskState } = subTask;

	// taskState is a Readable<TaskState>, so it can be observed but not modified
	// To update taskState, call: taskStateID.setValue(1);

	async function handleGrade(index: number) {
		const suffix_string = `?${page.url.searchParams.toString()}`;
		const url = new URL(
			`${window.location.origin}/tasks/${subTask.task.id}/grade/${index}${suffix_string}`
		);
		window.location.href = url.href;
	}
</script>

<tr>
	<td>{i}</td>
	<td
		class:unknown={$taskState.name == 'Unknown'}
		class:ready={$taskState.name == 'Ready'}
		class:busy={$taskState.name == 'Busy'}
	>
		{$taskState.name}
	</td>
	<td>
		<button onclick={() => handleGrade(i)}>View</button>
	</td>
	<td>
		<ul>
			{#each $instanceIds as instanceId}
				<li>{instanceId}</li>
			{/each}
		</ul>
	</td>
</tr>

<style>
	ul {
		margin: 0;
		padding-left: 0;
	}
	li {
		display: inline-block;
	}
	li:not(:first-child)::before {
		content: ', ';
	}
	td {
		padding-left: 0.8em;
        padding-right: 0.8em;
        padding-top: 0.4em;
        padding-bottom: 0.4em;
		border: 1px solid rgba(0, 0, 0, 0.1);
	}

	tr:nth-child(even) {
		background-color: #f8f8f8;
	}

	tr:nth-child(odd) {
		background-color: #fdfdfd;
	}

	tr:hover {
		background-color: #e0e0e0;
	}

	td.ready {
		background-color: greenyellow;
	}

	td.busy {
		background-color: orange;
	}

	td.unknown {
		background-color: lightgray;
	}
</style>
