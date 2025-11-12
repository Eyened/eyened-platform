<script lang="ts">
	import { fetchSubTaskByIndex, fetchTask } from "../../../../../lib/data/api";
	import { tasks, subtasks } from "../../../../../lib/data/stores.svelte";
	import TaskMain from "../../../../../lib/tasks/TaskMain.svelte";
	import type {
		SubTaskWithImagesGET,
		TaskGET,
	} from "../../../../../types/openapi_types";

	let { data } = $props();
	const { taskid, subTaskIndex } = data;

	// Store IDs after loading
	let taskId: number | null = $state(null);
	let subTaskId: number | null = $state(null);

	// Derive task and subtask from stores (will react to store updates)
	const task = $derived(taskId ? tasks.get(taskId) : undefined);
	const subTask = $derived(subTaskId ? subtasks.get(subTaskId) : undefined);

	const loadPromise: Promise<{
		task: TaskGET;
		subTask: SubTaskWithImagesGET;
		instanceIDs: number[];
	}> = (async () => {
		const [task, subTask] = await Promise.all([
			fetchTask(Number(taskid)),
			fetchSubTaskByIndex(Number(taskid), Number(subTaskIndex), {
				with_images: true,
			}),
		]);
		if (!subTask) throw new Error("Subtask not found");
		if (!("images" in subTask))
			throw new Error("Subtask missing images; ensure with_images=true");

		// Store IDs so we can derive from stores
		taskId = task.id;
		subTaskId = subTask.id;

		const instanceIDs = subTask.images.map((img) => img.id);
		return { task, subTask, instanceIDs };
	})();
</script>

<svelte:head>
	<title>Task {taskid} - {subTaskIndex}</title>
</svelte:head>

{#await loadPromise}
	<p>Loading subtask...</p>
{:then loaded}
	{#if task && subTask}
		<TaskMain {task} {subTask} {subTaskIndex} />
	{:else}
		<p>Error: Task or subtask not found in store</p>
	{/if}
{:catch e}
	<p>Error: {e?.message ?? String(e)}</p>
{/await}
