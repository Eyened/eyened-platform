<script lang="ts">
	import { page } from "$app/state";
	import { updateSubTask } from "$lib/data/api";
	import { subtasks } from "$lib/data/stores.svelte";
	import { subTaskStates } from "../../types/openapi_constants";
	import type {
		SubTaskState,
		SubTaskWithImagesGET,
		TaskGET,
	} from "../../types/openapi_types";

	interface Props {
		task: TaskGET;
		subTask: SubTaskWithImagesGET;
		subTaskIndex: number;
	}

	let { task, subTask, subTaskIndex }: Props = $props();

	const currentSubTask = $derived(
		(subtasks.get(subTask.id) as any) ?? (subTask as any),
	);

	async function setState(state: SubTaskState) {
		await updateSubTask(subTask.id, { task_state: state });
	}

	async function handleViewTask() {
		const suffix_string = `?${page.url.searchParams.toString()}`;
		const url = new URL(
			`${window.location.origin}/tasks/${task.id}${suffix_string}`,
		);
		window.location.href = url.href;
	}

	function navigateSubtaskIndex(index: number, searchParams: URLSearchParams) {
		const currentUrl = window.location.href;
		const lastSlashIndex = currentUrl.lastIndexOf("/");
		const suffix_string = `?${searchParams.toString()}`;
		const newUrl =
			currentUrl.substring(0, lastSlashIndex + 1) + index + suffix_string;
		window.location.href = newUrl;
	}

	function navigate(delta: number) {
		const searchParams = page.url.searchParams;
		searchParams.delete("annotation");
		searchParams.delete("instances");
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
	<div class="main">
		Task {task.name}. Set {subTaskIndex} of {task.num_tasks}.
	</div>
	<div class="controls center">
		Set status:
		{#each subTaskStates as state}
			{#if currentSubTask?.task_state == state}
				<button type="button" class="set">{state}</button>
			{:else}
				<button type="button" onclick={() => setState(state)}>
					{state}
				</button>
			{/if}
		{/each}
	</div>
	<div class="controls right">
		<button type="button" onclick={handleViewTask}>Overview</button>
		<button type="button" onclick={prev} disabled={subTaskIndex == 0}>
			Previous
		</button>
		<button
			type="button"
			onclick={next}
			disabled={subTaskIndex == task.num_tasks - 1}>Next</button
		>
	</div>
</div>

<style>
	div {
		display: flex;
		flex-direction: row;
	}
	div#main {
		display: flex;
		flex: 1;
		align-items: center;
	}

	div.main,
	div.controls {
		flex: 1;
		align-items: center;
	}
	div.right {
		flex-direction: row-reverse;
	}
	button {
		color: black;
		background-color: bisque;
		border: 1px solid bisque;
		border-radius: 2px;
		padding: 0.2em;
		margin: 0.2em;
	}
	button.set {
		background-color: rgb(235, 102, 53);
	}
	button:not(:disabled):hover {
		background-color: rgb(235, 153, 53);
	}
</style>
