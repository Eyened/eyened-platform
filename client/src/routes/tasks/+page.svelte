<script lang="ts">
	import Main from '$lib/components/Main.svelte';
	import * as Tooltip from "$lib/components/ui/tooltip";
	import { TasksRepo } from "$lib/data/repos.svelte";
	import TasksTable from "$lib/tasks/TasksTable.svelte";
	import { onMount } from "svelte";

	const repo = new TasksRepo('task');

	onMount(async () => {
		await repo.fetchAll();
	});
</script>

<Main>
	{#snippet children()}
		<div style="display:flex; justify-content:center; padding: 40px;">
			<div style="width: 100%; max-width: 1440px;">
				<h2 class="text-2xl font-bold mb-6">Tasks</h2>
				<Tooltip.Provider>
					<TasksTable rows={repo.all} {repo} />
				</Tooltip.Provider>
			</div>
		</div>
	{/snippet}
</Main>

