<script lang="ts">
	import Main from "$lib/components/Main.svelte";
	import * as Tooltip from "$lib/components/ui/tooltip";
	import TasksTable from "$lib/tasks/TasksTable.svelte";
	import { fetchTasks } from "$lib/data/api";

	const loading = fetchTasks().catch((error) => {
		console.error('Failed to fetch tasks:', error);
		// Error is logged, but we don't redirect here since fetchWithAuthRetry
		// already handles redirects for authentication errors
		throw error;
	});
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
	{:catch error}
		<div style="display:flex; justify-content:center; padding: 40px;">
			<div style="width: 100%; max-width: 1440px;">
				<h2 class="text-2xl font-bold mb-6">Tasks</h2>
				<p class="text-red-600">Failed to load tasks: {error.message}</p>
				<p class="text-sm text-gray-600 mt-2">
					If you were redirected to login, please log in and try again.
				</p>
			</div>
		</div>
	{/await}
</Main>
