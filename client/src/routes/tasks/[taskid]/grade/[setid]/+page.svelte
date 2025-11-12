<script lang="ts">
	import { fetchSubTaskByIndex, fetchTask } from "../../../../../lib/data/api";
	import TaskMain from "../../../../../lib/tasks/TaskMain.svelte";
	import type {
		SubTaskWithImagesGET,
		TaskGET,
	} from "../../../../../types/openapi_types";

	let { data } = $props();
	const { taskid, subTaskIndex } = data;

	const taskConfig = {};

	const loadPromise: Promise<{
		task: TaskGET;
		subTask: SubTaskWithImagesGET;
		instanceIDs: number[];
	}> = (async () => {
		const [task, subTask] = await Promise.all([
			fetchTask(Number(taskid)),
			fetchSubTaskByIndex(Number(taskid), Number(subTaskIndex), { with_images: true }),
		]);
		if (!subTask) throw new Error("Subtask not found");
		if (!("images" in subTask)) throw new Error("Subtask missing images; ensure with_images=true");
		const instanceIDs = subTask.images.map(img => img.id);
		return { task, subTask, instanceIDs };
	})();
</script>

<svelte:head>
	<title>Task {taskid} - {subTaskIndex}</title>
</svelte:head>

{#await loadPromise}
	<p>Loading subtask...</p>
{:then loaded}
	<TaskMain task={loaded.task} subTask={loaded.subTask} {subTaskIndex} {taskConfig} />
{:catch e}
	<p>Error: {e?.message ?? String(e)}</p>
{/await}
