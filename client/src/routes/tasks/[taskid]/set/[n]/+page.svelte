<script lang="ts">
    import { onMount } from "svelte";
    import {
        fetchSubTaskByIndex,
        fetchTask,
    } from "../../../../../lib/data/api";
    import { tasks, subtasks } from "../../../../../lib/data/stores.svelte";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import TaskMain from "../../../../../lib/tasks/TaskMain.svelte";
    import type {
        SubTaskWithImagesGET,
        TaskGET,
    } from "../../../../../types/openapi_types";

    let { data } = $props();
    const { taskid, setNumber } = data;
    // The URL counts from 1; the API and TaskContext from 0.
    const subTaskIndex = setNumber - 1;

    // Back can restore a set from the browser's cache with a stale status or a stuck button; reload it.
    onMount(() => {
        const reload = (event: PageTransitionEvent) => {
            if (event.persisted) window.location.reload();
        };
        window.addEventListener("pageshow", reload);
        return () => window.removeEventListener("pageshow", reload);
    });

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
    <title>Set {setNumber} · Task {taskid}</title>
</svelte:head>

{#await loadPromise}
    <div
        class="flex h-full items-center-safe justify-center overflow-y-auto p-4"
    >
        <InlineLoading
            class="w-auto"
            status="active"
            description="Loading task…"
        />
    </div>
{:then}
    {#if task && subTask}
        <TaskMain {task} {subTask} {subTaskIndex} />
    {:else}
        <div
            class="flex h-full items-center-safe justify-center overflow-y-auto p-4"
        >
            <InlineNotification
                class="max-w-112 break-words"
                title="Task failed to load"
                subtitle="Task or sub-task not found."
            />
        </div>
    {/if}
{:catch e}
    <div
        class="flex h-full items-center-safe justify-center overflow-y-auto p-4"
    >
        <InlineNotification
            class="max-w-112 break-words"
            title="Task failed to load"
            subtitle={e?.message ?? String(e)}
        />
    </div>
{/await}
