<script lang="ts">
    import { TaskDefinition } from "$lib/datamodel/taskDefinition";
    import { Task } from "$lib/datamodel/task.svelte";
    import { data } from "$lib/datamodel/model";
    import { getContext } from "svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const { creator } = globalContext;

    const tasks = data.tasks;
    const taskDefinitions = data.taskDefinitions;

    let newTaskName: string | undefined = $state();
    let newTaskDefinition: TaskDefinition | undefined = $state();
    let newTaskDefinitionName: string | undefined = $state();
    let newTaskDescription: string | undefined = $state();

    const admin = creator.isAdmin;

    async function handleSubmitAddTask(event: Event) {
        event.preventDefault();
        if (newTaskName && newTaskDefinition) {
            const item = {
                name: newTaskName,
                description: newTaskDescription,
                definitionId: newTaskDefinition.id,
            };
            const resp = await Task.create(item);
            console.log(resp);
        }
    }

    async function handleSubmitTaskType(event: Event) {
        event.preventDefault();
        if (newTaskDefinitionName) {
            const item = {
                name: newTaskDefinitionName,
            };
            const resp = await TaskDefinition.create(item);
        }
    }

    function remove(task: Task) {
        task.delete();
    }
</script>

<div id="main">
    <h2>Tasks:</h2>

    <ul>
        {#each $tasks as task}
            <li>
                <!-- These are currently preloaded when hovering. If that causes issues, consider adding  data-sveltekit-preload-data="tap"  -->
                <a
                    href={`${window.location.origin}/tasks/${task.id}${window.location.search}`}
                >
                    {task.name} (ID {task.id})
                </a>
                {#if admin}
                    <button onclick={() => remove(task)}> Remove </button>
                {/if}
            </li>
        {/each}
    </ul>

    <h3>Add task:</h3>
    <form onsubmit={handleSubmitAddTask}>
        Taskname:
        <input bind:value={newTaskName} type="text" />
        Description:
        <input bind:value={newTaskDescription} type="text" />
        Type:
        <select bind:value={newTaskDefinition}>
            {#each $taskDefinitions as taskDefinition}
                <option value={taskDefinition}> {taskDefinition.name} </option>
            {/each}
        </select>
        <button type="submit" disabled={!(newTaskName && newTaskDescription && newTaskDefinition)}>
            Add
        </button>
    </form>

    {#if admin}
        <h3>Add task definition:</h3>
        <form onsubmit={handleSubmitTaskType}>
            Taskdefinition name:
            <input bind:value={newTaskDefinitionName} type="text" />

            <button type="submit"> Add </button>
        </form>
    {/if}
</div>

<style>
    div#main {
        padding: 10vw;
        display: flex;
        flex: 1;
        flex-direction: column;
    }
    form {
        display: grid;
        grid-template-columns: max-content max-content;
    }
</style>
