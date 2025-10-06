<script lang="ts">
	import { TasksRepo } from "$lib/data/repos.svelte";
	import { onMount } from "svelte";
	import TaskMain from "../../../../../lib/tasks/TaskMain.svelte";
	import type { SubTaskWithImagesGET, TaskGET } from "../../../../../types/openapi_types";

	let { data } = $props();
	const { taskid, subTaskIndex } = data;

	const tasksRepo = new TasksRepo('tasks');

	let task= $state<TaskGET | null>(null);
	let subTask = $state<SubTaskWithImagesGET | null>(null);
	let error = $state<string | null>(null);

	const taskConfig = {};
	let instanceIDs = $state<number[]>([]);

	onMount(async () => {
		try {
			({ $: task } = await tasksRepo.fetchOne(taskid));
			const st = await tasksRepo.fetch_subtask(taskid, subTaskIndex, true, true);
			if (!('images' in st)) throw new Error("Subtask missing images; ensure with_images=true");
			subTask = st;
			instanceIDs = st.images.map(img => img.id);
		} catch (e: any) {
			error = e?.message ?? String(e);
		}
	});
</script>

<svelte:head>
	<title>Task {taskid} - {subTaskIndex}</title>
</svelte:head>

{#if error}
	<p>Error: {error}</p>
{:else if !subTask}
	<p>Loading subtask...</p>
{:else}
	<TaskMain task={task as TaskGET} {subTask} subTaskIndex={subTaskIndex} taskConfig={taskConfig} />
{/if}
