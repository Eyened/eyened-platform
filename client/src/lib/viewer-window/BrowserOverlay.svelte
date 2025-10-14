<script lang="ts">
	import { goto } from "$app/navigation";
	import { page } from "$app/state";
	import BrowserContent from "$lib/browser/BrowserContent.svelte";
	import { BrowserContext } from "$lib/browser/browserContext.svelte";
	import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
	import {
		addSubTaskImage,
		removeSubTaskImage,
	} from "$lib/data/helpers";
	import { instances } from "$lib/data/stores.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import { getContext, onMount, setContext } from "svelte";
	import type { InstanceGET } from "../../types/openapi_types";
	import { ViewerWindowContext } from "./viewerWindowContext.svelte";

	interface Props {
		viewerWindowContext: ViewerWindowContext;
	}

	let { viewerWindowContext }: Props = $props();
	const initialInstanceIds = viewerWindowContext.instanceIds.slice();

	const browserContext = new BrowserContext();
	browserContext.selectedIds = initialInstanceIds;

	setContext("browserContext", browserContext);

	console.log("BrowserOverlay", browserContext.selectedIds);

	const taskContext = getContext<TaskContext>("taskContext");
	const subTask = taskContext?.subTask;

	// whether to update the image links in the database
	let updateImageLinks = $state(false);

	// Track search status
	let isSearching = $state(false);

	// Automatically search for patient identifiers when component mounts
	onMount(async () => {
		await performPatientIdentifierSearch();
	});

	async function performPatientIdentifierSearch() {
		isSearching = true;

		try {
			// Extract unique patient identifiers from selected instances
			const patientIdentifiers = new Set<string>();

			// Get instances from the data stores using the instance IDs
			for (const instanceId of initialInstanceIds) {
				const instance = instances.get(instanceId) as InstanceGET;
				if (instance) {
					if (instance.patient?.identifier) {
						patientIdentifiers.add(instance.patient.identifier);
					}
				} else {
					console.error("Instance not found", instanceId);
				}
			}

			// If we found patient identifiers, search for all instances from those patients
			if (patientIdentifiers.size > 0) {
				const patientIdsArray = Array.from(patientIdentifiers);
				const conditions = [
					{
						variable: "Patient Identifier" as const,
						operator: "IN" as const,
						value: patientIdsArray,
					},
				];

				// Set up browser context for search
				browserContext.queryMode = "instances";
				browserContext.displayMode = "instance";
				browserContext.limit = 100; // Show more results for patient search
				browserContext.page = 0;

				// Perform the search
				await browserContext.fetch(conditions, false);
			}
		} finally {
			isSearching = false;
		}
	}

	function close() {
		viewerWindowContext.closeBrowserOverlay();

		const currentInstanceIds = [...browserContext.selectedIds];
		if (subTask) {
			if (updateImageLinks) {
				updateSubTaskImageLinks(currentInstanceIds);
			}
		} else {
			// updates url (just visual, does not reload the page)
			const searchParams = page.url.searchParams;
			searchParams.set("instances", currentInstanceIds.join(","));
			goto(`?${page.url.searchParams.toString()}`.replaceAll("%2C", ","));
		}
		viewerWindowContext.setInstanceIDs(currentInstanceIds);
	}

	async function updateSubTaskImageLinks(currentInstanceIds: number[]) {
		const newInstanceIds = currentInstanceIds.filter(
			(id) => !initialInstanceIds.includes(id),
		);
		const removedInstanceIds = initialInstanceIds.filter(
			(id) => !currentInstanceIds.includes(id),
		);

		const taskId = subTask!.task_id;
		const subtaskIndex = subTask!.index ?? 0;

		for (const instanceId of newInstanceIds) {
			await addSubTaskImage(taskId, subtaskIndex, instanceId);
		}
		for (const instanceId of removedInstanceIds) {
			await removeSubTaskImage(taskId, subtaskIndex, instanceId);
		}
	}
</script>

<div id="browser-overlay">
	<div class="button-container">
		{#if subTask}
			<label for="updateImageLinks">Update task image links</label>
			<input
				id="updateImageLinks"
				type="checkbox"
				bind:checked={updateImageLinks}
			/>
		{/if}
		<button class="close-button" onclick={close}>Close</button>
	</div>
	<div id="selection">
		{#each browserContext.selectedInstances as instance (instance.id)}
			<InstanceComponent {instance} />
		{/each}
	</div>
	<div id="content">
		{#if isSearching}
			<div class="loading-message">Searching for patient images...</div>
		{:else}
			<BrowserContent mode="overlay" />
		{/if}
	</div>
</div>

<style>
	div#browser-overlay {
		position: fixed;
		z-index: 100;
		left: 0;
		top: 0;
		bottom: 0;
		right: 0;
		background-color: rgba(255, 255, 255, 0.8);
		backdrop-filter: blur(10px); /* Add this line */

		transition: 0.5s;
		display: flex;
		flex-direction: column;
	}
	div#content {
		flex: 1;
		display: flex;
		flex-direction: column;
		padding: 1em;
		overflow-y: auto;
	}
	div#selection {
		display: flex;
		background-color: black;
	}
	.button-container {
		display: flex;
		justify-content: center;
		padding: 20px;
	}
	label {
		align-self: center;
	}
	.close-button {
		background-color: #85c1e9;
		color: #333;
		font-size: 18px;
		padding: 10px 24px;
		border: none;
		cursor: pointer;
		border-radius: 5px;
		transition: 0.3s;
	}
	.close-button:hover {
		background-color: #6cb6e7; /* Darker blue on hover */
	}
	.loading-message {
		display: flex;
		justify-content: center;
		align-items: center;
		height: 200px;
		font-size: 18px;
		color: #666;
		background-color: rgba(255, 255, 255, 0.9);
		border-radius: 8px;
		margin: 20px;
	}
</style>
