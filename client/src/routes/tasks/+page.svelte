<script lang="ts">
	import Main from "$lib/components/Main.svelte";
	import * as Tooltip from "$lib/components/ui/tooltip";
	import TasksTable from "$lib/tasks/TasksTable.svelte";
	import { onMount } from "svelte";
	import { fetchTasks } from "$lib/data/api";
	import { tasks } from "$lib/data/stores.svelte";

	// Derive tasks array from global store
	let tasksArray = $derived(Array.from(tasks.values()));

	onMount(async () => {
		await fetchTasks();
	});
</script>

<Main>
	{#snippet children()}
		<div style="display:flex; justify-content:center; padding: 40px;">
			<div style="width: 100%; max-width: 1440px;">
				<h2 class="text-2xl font-bold mb-6">Tasks</h2>
				<Tooltip.Provider>
					<TasksTable rows={tasksArray} />
				</Tooltip.Provider>
			</div>
		</div>
	{/snippet}
</Main>
