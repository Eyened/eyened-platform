<script lang="ts">
	import TaskMain from '$lib/tasks/TaskMain.svelte';
	import { data as modelData } from '$lib/datamodel/model.js';
	import { loadSubtasks } from '$lib/datamodel/api.js';
	import { derived } from 'svelte/store';

	let { data } = $props();

	const { subTaskIndex, taskid } = data;

	const task = modelData.tasks.find((t) => t.id == taskid);
	if (task) {
		loadSubtasks(task);
	}
	const subtasks = modelData.subTasks.filter((st) => st.task == task);
	const subTask = derived(subtasks, ($subtasks) => {
		if ($subtasks.length > subTaskIndex) {
			return $subtasks[subTaskIndex];
		}
		return undefined;
	});

	let taskConfig: any = {};
	if (task?.id == 25) {
		taskConfig.showOtherAnnotationsHuman = false;
		taskConfig.showOtherAnnotationsMachine = false;
        taskConfig.hideOptio = true;
	}
</script>

<svelte:head>
	<title>Eyened viewer: task {taskid}</title>
</svelte:head>
{#if task}
	{#if $subTask}
		<TaskMain {task} subTask={$subTask} {subTaskIndex} {taskConfig} />
	{:else}
		<p>Subtask not found</p>
	{/if}
{:else}
	<p>Task not found</p>
{/if}
