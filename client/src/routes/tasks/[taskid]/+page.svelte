<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import Main from '$lib/components/Main.svelte';
	import { SubTasksRepo } from '$lib/data/repos.svelte';
	import SubtasksTable from '$lib/tasks/SubtasksTable.svelte';
	import { onMount } from 'svelte';

	let { data } = $props();

	let task: any = $state(null);
	let subtasksRepo: any = $state(null);
	let subtasks = $derived(subtasksRepo?.all || []);

	onMount(async () => {
		// Create subtasks repo and load subtasks
		subtasksRepo = new SubTasksRepo(`task-${data.taskid}-subtasks`);
		await subtasksRepo.fetchAll({ 
			task_id: data.taskid, 
			with_images: true, 
			limit: 200, 
			page: 0 
		});
		
		// For now, create a simple task object with the basic info
		task = { $: { name: `Task ${data.taskid}`, task_state: 'Loading...' } };
	});

	function deselect() {
		const currentUrl = window.location.href;
		const lastSlashIndex = currentUrl.lastIndexOf('/');

		const suffix_string = `?${page.url.searchParams.toString()}`;
		const newUrl = currentUrl.substring(0, lastSlashIndex + 1) + suffix_string;

		goto(newUrl);
	}
</script>

<Main>
	{#snippet children()}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div id="main">
			<h3><span onclick={deselect} onkeypress={deselect}> ... </span></h3>
			{#if !task}
				Task not found
			{:else}
				<h1>{task.$.name}</h1>
				{#if task.$.task_state}
					<h3>Status: {task.$.task_state}</h3>
				{/if}
				{#if subtasksRepo}
					<SubtasksTable rows={subtasks} repo={subtasksRepo} taskId={data.taskid} />
				{/if}
			{/if}
		</div>
	{/snippet}
</Main>

<style>
	span {
		cursor: pointer;
		font-size: large;
		font-weight: bold;
	}
	div#main {
		display: flex;
		padding: 3em;
		flex-direction: column;
		overflow: auto;
	}
</style>
