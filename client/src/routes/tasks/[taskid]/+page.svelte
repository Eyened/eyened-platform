<script lang="ts">
	import { goto } from '$app/navigation';
	import { page as appPage } from '$app/state';
	import FixedSpinner from '$lib/components/FixedSpinner.svelte';
	import Main from '$lib/components/Main.svelte';
	import { SubTasksRepo, TasksRepo } from '$lib/data/repos.svelte';
	import SubtasksTable from '$lib/tasks/SubtasksTable.svelte';
	import { onMount } from 'svelte';

	let { data } = $props();

	let task: any = $state(null);
	let isLoading: boolean = $state(true);
	const subtasksRepo =new SubTasksRepo(`subtasks`);
	let subtasks = $derived(subtasksRepo?.all || []);

	// Pagination metadata state
	let subtasksCount: number = $state(0);
	let subtasksLimit: number = $state(200);
	let subtasksPage: number = $state(0);

	async function loadPage(p: number): Promise<void> {
		isLoading = true;
		try {
			const tasksRepo = new TasksRepo('tasks');
			const nextPage = Math.max(0, Number.isFinite(p) ? p : 0);

			const res = await tasksRepo.listSubtasks({
				task_id: data.taskid,
				with_images: true,
				limit: subtasksLimit,
				page: nextPage
			});

			subtasksRepo.clear();
			subtasksRepo.ingest(res.subtasks);
			subtasksCount = res.count;
			subtasksLimit = res.limit;
			subtasksPage = res.page;

			const url = new URL(window.location.href);
			url.searchParams.set('page', String(subtasksPage));
			url.searchParams.set('limit', String(subtasksLimit));
			await goto(url.pathname + '?' + url.searchParams.toString(), {
				replaceState: true,
				noScroll: true,
				keepFocus: true
			});
		} finally {
			isLoading = false;
		}
	}

	onMount(async () => {
		try {
			const sp = appPage.url.searchParams;
			const qpLimit = Number(sp.get('limit'));
			const qpPage = Number(sp.get('page'));

			if (Number.isFinite(qpLimit) && qpLimit > 0) subtasksLimit = qpLimit;
			if (Number.isFinite(qpPage) && qpPage >= 0) subtasksPage = qpPage;

			await loadPage(subtasksPage);
			
			// For now, create a simple task object with the basic info
			task = { $: { name: `Task ${data.taskid}`, task_state: 'Loading...' } };
		} catch (error) {
			console.error('Error loading task page:', error);
			isLoading = false;
		}
	});

	function deselect() {
		const currentUrl = window.location.href;
		const lastSlashIndex = currentUrl.lastIndexOf('/');

		const suffix_string = `?${appPage.url.searchParams.toString()}`;
		const newUrl = currentUrl.substring(0, lastSlashIndex + 1) + suffix_string;

		goto(newUrl);
	}
</script>

{#if isLoading}
	<FixedSpinner />
{/if}

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
					<SubtasksTable
						rows={subtasks}
						repo={subtasksRepo}
						taskId={data.taskid}
						count={subtasksCount}
						page={subtasksPage}
						perPage={subtasksLimit}
						onPageChange={loadPage}
					/>
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
		width: 100%;
		max-width: 1440px;
		margin: 0 auto;
		display: flex;
		padding: 1em 3em;
		flex-direction: column;
		overflow: auto;
	}
</style>
