<script lang="ts">
    import { browser } from "$app/environment";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { data } from "$lib/datamodel/model";
    import { SubTask } from "$lib/datamodel/subTask.svelte";
    import type { Task } from "$lib/datamodel/task.svelte";
    import { get_url_params } from "$lib/utils";
    import SubTaskRow from "./SubTaskRow.svelte";

    import { getContext } from "svelte";

    interface Props {
        task: Task;
    }

    let { task }: Props = $props();

    const { creator } = getContext<GlobalContext>("globalContext");

    const content = task.subTasks;

    const states = data.taskStates;

    let filterStateId: number | undefined = $state(undefined);
    let selectedContent = $derived.by(() => {
        if (filterStateId != undefined) {
            return content.filter(
                (subTask) => subTask.taskStateId === filterStateId,
            );
        } else {
            return content;
        }
    });

    let selectionStart = $state(0);
    let selectionSize = 100;

    function next() {
        selectionStart = selectionStart + selectionSize;
    }

    function previous() {
        selectionStart = selectionStart - selectionSize;
    }

    let admin = false;
    if (browser) {
        const params = get_url_params();
        admin = Boolean(params.admin);
    }

    function addSubTask() {
        const taskState = data.taskStates.find(
            (state) => state.name == "Not started",
        )!;        
        const item = {
            taskId: task.id,
            taskStateId: taskState.id,
            creatorId: creator.id,
        };
        SubTask.create(item);
    }
</script>

Viewing sets {selectionStart + 1} to {Math.min(
    selectionStart + selectionSize,
    $selectedContent.length,
)} of {$selectedContent.length}.
<nav>
    {#if selectionStart > 0}
        <button onclick={() => previous()}>Previous</button>
    {/if}

    {#if selectionStart + selectionSize < $selectedContent.length}
        <button onclick={() => next()}>Next</button>
    {/if}
</nav>
<div class="sample">
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>
                    State
                    <select bind:value={filterStateId}>
                        <option value={undefined}>[all]</option>
                        {#each $states as state}
                            <option value={state.id}>{state.name}</option>
                        {/each}
                    </select>
                </th>
                <th></th>
                <th>Images</th>
                <th>Comments</th>
            </tr>
        </thead>
        <tbody>
            {#each $selectedContent.slice(selectionStart, Math.min(selectionStart + selectionSize, $selectedContent.length)) as subTask, i (subTask.id)}
                <SubTaskRow i={$content.indexOf(subTask)} {subTask} />
            {/each}
        </tbody>
    </table>
    <button onclick={addSubTask}>Add SubTask</button>
</div>
<nav>
    {#if selectionStart > 0}
        <button onclick={() => previous()}>Previous</button>
    {/if}

    {#if selectionStart + selectionSize - 1 < $selectedContent.length}
        <button onclick={() => next()}>Next</button>
    {/if}
</nav>

<style>
    nav {
        display: flex;
        margin-top: 1em;
        margin-bottom: 1em;
    }
    .sample {
        border: 0px;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        border: 1px solid black;
    }
    th {
        padding: 0.8em;
        border: 1px solid rgba(0, 0, 0, 0.1);
    }

    thead {
        background-color: black;
        color: white;
    }
</style>
