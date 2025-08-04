<script lang="ts">
	import TaskTableView from '$lib/tasks/TaskTableView.svelte';
	import { goto } from '$app/navigation';
	import { data as modelData } from '$lib/datamodel/model.js';
	import { loadSubtasks } from '$lib/utils/api';
	import { page } from '$app/state';

	let { data } = $props();

	const task = modelData.tasks.get(data.taskid);

	if (task) {
		loadSubtasks(task);
	}

	function deselect() {
		const currentUrl = window.location.href;
		const lastSlashIndex = currentUrl.lastIndexOf('/');

		const suffix_string = `?${page.url.searchParams.toString()}`;
		const newUrl = currentUrl.substring(0, lastSlashIndex + 1) + suffix_string;

		goto(newUrl);
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div id="main">
	<h3><span onclick={deselect} onkeypress={deselect}> ... </span></h3>
	{#if !task}
		Task not found
	{:else}
		<h1>{task.name}</h1>
		{#if task.state}
			<h3>Status: {task.state.name}</h3>
		{/if}
		<TaskTableView {task} />
	{/if}
</div>

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
