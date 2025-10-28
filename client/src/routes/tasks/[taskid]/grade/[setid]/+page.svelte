<script lang="ts">
	import { fetchSubTasks, fetchTask } from "../../../../../lib/data/api";
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
		const [task, subTasksResponse] = await Promise.all([
			fetchTask(Number(taskid)),
			fetchSubTasks({ task_id: Number(taskid), with_images: true }),
		]);
		const st = subTasksResponse?.subtasks?.[Number(subTaskIndex)];
		if (!st) throw new Error("Subtask not found");
		if (!("images" in st)) throw new Error("Subtask missing images; ensure with_images=true");
		const subTask = st as SubTaskWithImagesGET;
		const instanceIDs = subTask.images.map((img: any) => img.id);
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
