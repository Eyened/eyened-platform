<script lang="ts">
    import TaskMain from "$lib/tasks/TaskMain.svelte";
    import { data as modelData } from "$lib/datamodel/model.js";
    import { loadInstances, loadSubtasks } from "$lib/utils/api";
    import { Deferred } from "$lib/utils.js";
    import { onMount } from "svelte";
    import type { SubTask } from "$lib/datamodel/subTask.svelte.js";
    let { data } = $props();

    const { subTaskIndex, taskid } = data;

    const subTaskPromise = new Deferred<SubTask>();

    const task = modelData.tasks.get(taskid);
    onMount(async () => {
        if (!task) {
            subTaskPromise.reject(new Error("Task not found"));
            return;
        }
        await loadSubtasks(task);
        const subTask = task.subTasks.get$(subTaskIndex);
        if (!subTask) {
            subTaskPromise.reject(new Error("Subtask not found"));
            return;
        }
        await loadInstances(subTask.instances.map$((instance) => instance.id));

        subTaskPromise.resolve(subTask);
    });
    const taskConfig = {};
</script>

<svelte:head>
    <title>Task {taskid} - {subTaskIndex}</title>
</svelte:head>
{#await subTaskPromise.promise}
    <p>Loading subtask...</p>
{:then subTask}
    <TaskMain task={task!} {subTask} {subTaskIndex} {taskConfig} />
{:catch error}
    <p>Error: {error.message}</p>
{/await}
