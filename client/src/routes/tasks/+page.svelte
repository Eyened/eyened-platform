<script lang="ts">
	import Main from "$lib/components/Main.svelte";
	import * as Tooltip from "$lib/components/ui/tooltip";
	import TasksTable from "$lib/tasks/TasksTable.svelte";
	import { fetchTasks } from "$lib/data/api";

	const loading = fetchTasks();
</script>

<Main>
	{#await loading}
		<p>Loading tasks...</p>
	{:then tasks}
		<div style="display:flex; justify-content:center; padding: 40px;">
			<div style="width: 100%; max-width: 1440px;">
				<h2 class="text-2xl font-bold mb-6">Tasks</h2>
				<Tooltip.Provider>
					<TasksTable rows={tasks} />
				</Tooltip.Provider>
			</div>
		</div>
	{/await}
</Main>
