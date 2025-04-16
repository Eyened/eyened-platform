<script lang="ts">
	import { browser } from '$app/environment';
	import type { TaskDefinition } from '$lib/datamodel/taskDefinition';
	import type { Task } from '$lib/datamodel/task';
	import { data } from '$lib/datamodel/model';

	const tasks = data.tasks;
	const taskDefinitions = data.taskDefinitions;

	function get_url_params() {
		const urlSearchParams = new URLSearchParams(window.location.search);
		return Object.fromEntries(urlSearchParams.entries());
	}

	let newTaskName: string | undefined = $state();
	let newTaskDefinition: TaskDefinition | undefined = $state();
	let newTaskDefinitionName: string | undefined = $state();

	let admin = $state(false);
	if (browser) {
		const params = get_url_params();
		admin = Boolean(params.admin);		
	}

	async function handleSubmitAddTask(event: Event) {
		event.preventDefault();
		if (newTaskName && newTaskDefinition) {
			const item = {
				name: newTaskName,
				definition: newTaskDefinition
			};
			const resp = await tasks.create(item);            
		}
	}

	async function handleSubmitTaskType(event: Event) {
		event.preventDefault();
		if (newTaskDefinitionName) {
            const item = {
                name: newTaskDefinitionName,
            }
            const resp = await taskDefinitions.create(item);
		}
	}

	function remove(task: Task) {
		tasks.delete(task);
	}
</script>

<div id="main">
	<h2>Tasks:</h2>

	<ul>
		{#each $tasks as task}
			<li>
				<!-- These are currently preloaded when hovering. If that causes issues, consider adding  data-sveltekit-preload-data="tap"  -->
				<a href={`${window.location.origin}/tasks/${task.id}${window.location.search}`}>
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
		Type:
		<select bind:value={newTaskDefinition}>
			{#each $taskDefinitions as taskDefinition}
				<option value={taskDefinition}> {taskDefinition.name} </option>
			{/each}
		</select>
		<button type="submit"> Add </button>
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
