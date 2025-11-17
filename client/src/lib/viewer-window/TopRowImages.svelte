<script lang="ts">
	import Spinner from "$lib/components/Spinner.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import { TaskNavigation } from "$lib/tasks/taskUtils.svelte";
	import { getContext } from "svelte";
	import TopViewer from "./TopViewer.svelte";
	import type { ViewerWindowContext } from "./viewerWindowContext.svelte";

	import { Button } from "$lib/components/ui/button";
	import TaskOverlay from "$lib/tasks/TaskOverlay.svelte";
	import ChevronLeft from "@lucide/svelte/icons/chevron-left";
	import ChevronRight from "@lucide/svelte/icons/chevron-right";
	import BrowserOverlay from "./BrowserOverlay.svelte";
	import Task from "./icons/Task.svelte";

	const viewerWindowContext = getContext<ViewerWindowContext>(
		"viewerWindowContext",
	);
	const taskContext = getContext<TaskContext>("taskContext");
	let selectedPanel: "task" | "browser" | null = $state(null);

	const navigation = new TaskNavigation(taskContext);

	function selectPanel(panel: "task" | "browser" | null) {
		if (selectedPanel == panel) {
			selectedPanel = null;
		} else {
			selectedPanel = panel;
		}
	}
</script>

{#if viewerWindowContext.instanceIds.length == 0}
	<div class="empty">Enter instance IDs in url</div>
{:else}
	<div id="images">
		{#each viewerWindowContext.instanceIds as instanceId}
			{#await viewerWindowContext.getImages(instanceId)}
				<div class="itemLoading">
					<div>Loading {instanceId}</div>
					<Spinner />
				</div>
			{:then images}
				{#each images as image}
					<TopViewer {image} />
				{/each}
			{/await}
		{/each}
	</div>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<div
		id="panel"
		class:hidden={selectedPanel == null}
		tabindex="0"
		onpointerenter={(e) => e.target.focus()}
		onkeydown={(e) => {
			if (e.key == "Escape") {
				selectPanel(null);
			}
		}}
	>
		<div class="header">
			<Button variant="outline" size="sm" onclick={() => selectPanel(null)}>
				Close
			</Button>
		</div>
		<div>
			{#if selectedPanel == "task"}
				<TaskOverlay {taskContext} />
			{/if}
			{#if selectedPanel == "browser"}
				<BrowserOverlay {viewerWindowContext} />
			{/if}
		</div>
	</div>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div id="panel-selector">
		{#if taskContext}
			<div
				class="icon"
				class:disabled={navigation.prevDisabled}
				onclick={() => navigation.prev()}
			>
				<ChevronLeft />
			</div>
			<div
				class="icon"
				class:disabled={navigation.nextDisabled}
				onclick={() => navigation.next()}
			>
				<ChevronRight />
			</div>
			<div class="icon" onclick={() => selectPanel("task")}><Task /></div>
		{/if}
		<div class="icon" onclick={() => selectPanel("browser")}>+</div>
	</div>
{/if}

<style>
	div.empty {
		padding: 2em;
		flex: 1;
		background-color: white;
		color: black;
		z-index: 2;
	}
	div.itemLoading {
		display: flex;
		flex: 1;
		flex-direction: column;
		align-items: center;
		flex-direction: column;
		background-color: black;
		border: 1px solid black;
		border-right: 1px solid gray;
		color: white;
		padding-top: 2em;
		z-index: 2;
	}

	div#panel-selector {
		z-index: 3;
		display: flex;
		flex: 0;
		flex-direction: column;
	}

	div#panel {
		position: fixed;
		z-index: 1000;
		left: 0;
		top: 0;
		bottom: 0;
		right: 0;
		background-color: rgba(255, 255, 255, 0.9);
		backdrop-filter: blur(10px);
		display: flex;
		flex-direction: column;
		overflow-y: auto;
		/* Force light theme for all child components */
		color: #1a1a1a !important;
	}
	div#panel.hidden {
		display: none !important;
	}
	div#panel .header {
		display: flex;
		justify-content: right;
		padding: 0.2em;
	}
	div#images {
		flex: 1;
		flex-direction: row;
		display: flex;
	}
	div.icon {
		padding: 0.2em;
		color: rgba(255, 255, 255, 0.8);
		width: 2em;
		height: 2em;
		display: flex;
		align-items: center;
		justify-content: center;
		background-color: rgba(255, 255, 255, 0.3);
		margin: 0.2em;
		border-radius: 2px;
		user-select: none;
		cursor: pointer;
	}
	div.icon:hover:not(.disabled) {
		color: rgba(255, 255, 255, 1);
	}
	div.icon.disabled {
		opacity: 0.4;
		cursor: not-allowed;
		pointer-events: none;
	}
</style>
