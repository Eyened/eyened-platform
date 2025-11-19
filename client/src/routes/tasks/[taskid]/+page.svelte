<script lang="ts">
	import { goto } from '$app/navigation';
	import { page as appPage } from '$app/state';
	import FixedSpinner from '$lib/components/FixedSpinner.svelte';
	import Main from '$lib/components/Main.svelte';
	import SubtasksTable from '$lib/tasks/SubtasksTable.svelte';
	import { onMount } from 'svelte';
// Status filter UI
	import { ButtonGroup } from '$lib/components/ui/button-group';
	import Button from '$lib/components/ui/button/button.svelte';
	import { fetchSubTasks, fetchTask } from '$lib/data/api';
	import { subtasks, tasks } from '$lib/data/stores.svelte';
	import Label from '../../../lib/components/ui/label/label.svelte';
	import { subTaskStates } from '../../../types/openapi_constants';
	import type { SubTaskState } from '../../../types/openapi_types';

	let { data } = $props();

	let isLoading: boolean = $state(true);
	
	// Derive task from global store
	let task = $derived(tasks.get(data.taskid));
	
	// Derive subtasks array from global store
	let subtasksArray = $derived(Array.from(subtasks.values()));

	// Pagination metadata state
	let subtasksCount: number = $state(0);
	let subtasksLimit: number = $state(20);
	let subtasksPage: number = $state(0);

	// Status filter state
	let subtasksStatus: SubTaskState | null = $state(null);

	async function loadPage(p: number): Promise<void> {
		isLoading = true;
		try {
			await fetchTask(data.taskid);
			const nextPage = Math.max(0, Number.isFinite(p) ? p : 0);

			subtasks.clear()
			const res = await fetchSubTasks({
				task_id: data.taskid,
				with_images: true,
				limit: subtasksLimit,
				page: nextPage,
				subtask_status: subtasksStatus ?? undefined
			});

			subtasksCount = res.count;
			subtasksLimit = res.limit;
			subtasksPage = res.page;

			const url = new URL(window.location.href);
			url.searchParams.set('page', String(subtasksPage));
			url.searchParams.set('limit', String(subtasksLimit));
			if (subtasksStatus) url.searchParams.set('status', String(subtasksStatus));
			else url.searchParams.delete('status');
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
			const qpStatus = sp.get('status');

			if (Number.isFinite(qpLimit) && qpLimit > 0) subtasksLimit = qpLimit;
			if (Number.isFinite(qpPage) && qpPage >= 0) subtasksPage = qpPage;
			if (qpStatus && (subTaskStates as readonly string[]).includes(qpStatus)) {
				subtasksStatus = qpStatus as SubTaskState;
			}

			await loadPage(subtasksPage);
		} catch (error) {
			console.error('Error loading task page:', error);
			isLoading = false;
		}
	});

	function selectStatus(s: SubTaskState | null) {
		subtasksStatus = s;
		loadPage(0);
	}

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
{:else}
	<Main>
		{#snippet children()}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div id="main">
				<h3><span onclick={deselect} onkeypress={deselect}> ... </span></h3>
				{#if !task}
					Task not found
				{:else}
					<h1>{task.name}</h1>
					{#if task.task_state}
						<h3>Status: {task.task_state}</h3>
					{/if}
					    <Label>Status:</Label>
						<ButtonGroup class="mb-4">
							<Button
								variant={subtasksStatus === null ? 'default' : 'outline'}
								aria-pressed={subtasksStatus === null}
								onclick={() => selectStatus(null)}
							>
								All
							</Button>
							{#each subTaskStates as s}
								<Button
									variant={subtasksStatus === s ? 'default' : 'outline'}
									aria-pressed={subtasksStatus === s}
									onclick={() => selectStatus(s)}
								>
									{s}
								</Button>
							{/each}
						</ButtonGroup>
					<SubtasksTable
						rows={subtasksArray}
						taskId={data.taskid}
						count={subtasksCount}
						page={subtasksPage}
						perPage={subtasksLimit}
						onPageChange={loadPage}
					/>
				{/if}
			</div>
		{/snippet}
	</Main>
{/if}



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
