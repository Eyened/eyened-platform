<script lang="ts">
	import { page } from '$app/state';
	import { data } from '$lib/datamodel/model';
	import type { TaskState } from '$lib/datamodel/taskState';
	import type { TaskContext } from '$lib/types';
	import { getContext } from 'svelte';

	const { taskStates } = data;
	const stateNames = ['Not started', 'Busy', 'Ready'];
	const states = stateNames.map((name) => taskStates.find((state) => state.name === name)!);
	const { task, subTask, subTaskIndex } = getContext<TaskContext>('taskContext');

	const subtasks = task.subTasks;

	function setState(state: TaskState) {
		subTask.update({ taskStateId: state.id });
	}

	async function handleViewTask() {
		const suffix_string = `?${page.url.searchParams.toString()}`;
		const url = new URL(`${window.location.origin}/tasks/${task.id}${suffix_string}`);
		window.location.href = url.href;
	}

	function navigateSubtaskIndex(index: number, searchParams: URLSearchParams) {
		const currentUrl = window.location.href;
		const lastSlashIndex = currentUrl.lastIndexOf('/');
		const suffix_string = `?${searchParams.toString()}`;
		const newUrl = currentUrl.substring(0, lastSlashIndex + 1) + index + suffix_string;
		window.location.href = newUrl;
	}

	function navigate(delta: number) {
		const searchParams = page.url.searchParams;
		searchParams.delete('annotation');
		searchParams.delete('instances');
		navigateSubtaskIndex(subTaskIndex + delta, searchParams);
	}

	function prev() {
		navigate(-1);
	}

	function next() {
		navigate(1);
	}
</script>

<div id="main">
	<div class="spacer"></div>
	<div class="main">
		Task {task.name}. Set {subTaskIndex} of {$subtasks.length}.
	</div>
	<div class="controls">
		Set status:
		{#each states as state}
			{#if subTask.state == state}
				<button class="set">{state.name}</button>
			{:else}
				<button onclick={() => setState(state)}>{state.name}</button>
			{/if}
		{/each}
	</div>
	<div class="controls">
		<button onclick={handleViewTask}>Overview</button>
		<button onclick={prev} disabled={subTaskIndex == 0}>Previous</button>
		<button onclick={next} disabled={subTaskIndex == $subtasks.length - 1}>Next</button>
	</div>
	<div class="spacer"></div>
</div>

<style>
	div#main {
		display: flex;
		flex: 1;
		align-items: center;
		padding: 0.5em;
	}
	div#main > div.spacer {
		flex: 0.2;
	}
	div.main {
		flex: 1;
	}
	div.controls {
		flex: 1;
		text-align: right;
	}
	button {
		background-color: bisque;
		border: 1px solid black;
	}
	button.set {
		background-color: rgb(235, 102, 53);
	}
	button:not(:disabled):hover {
		background-color: rgb(235, 153, 53);
	}
</style>
