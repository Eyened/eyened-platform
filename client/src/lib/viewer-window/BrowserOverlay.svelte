<script lang="ts">
	import BrowserContent from "$lib/browser/BrowserContent.svelte";
	import { BrowserContext } from "$lib/browser/browserContext.svelte";
	import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
	import { addSubTaskImage, removeSubTaskImage } from "$lib/data/helpers";
	import { instances } from "$lib/data/stores.svelte";
	import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
	import { getContext, setContext } from "svelte";
	import type { InstanceGET } from "../../types/openapi_types";
	import { ViewerWindowContext } from "./viewerWindowContext.svelte";

	interface Props {
		viewerWindowContext: ViewerWindowContext;
	}

	let { viewerWindowContext }: Props = $props();
	const initialInstanceIds = viewerWindowContext.instanceIds.slice();
	const browserContext = new BrowserContext();

	setContext("browserContext", browserContext);

	const taskContext = getContext<TaskContext>("taskContext");
	const subTask = taskContext?.subTask;

	// whether to update the image links in the database
	let updateImageLinks = $state(false);

	async function performPatientIdentifierSearch() {
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
					type: "default" as const,
					variable: "Patient Identifier" as const,
					operator: "IN" as const,
					value: patientIdsArray,
				},
			];

			// Set up browser context for search
			browserContext.queryMode = "studies";
			browserContext.displayMode = "study";
			browserContext.limit = 100; // Show more results for patient search
			browserContext.page = 0;

			// Perform the search
			await browserContext.fetch(conditions, false);

			// Set the initial selection after search completes
			browserContext.selectedIds = [...initialInstanceIds];
		}
	}

	const searching = performPatientIdentifierSearch();

	async function updateSubTaskImageLinks(currentInstanceIds: number[]) {
		const newInstanceIds = currentInstanceIds.filter(
			(id) => !initialInstanceIds.includes(id),
		);
		const removedInstanceIds = initialInstanceIds.filter(
			(id) => !currentInstanceIds.includes(id),
		);

		for (const instanceId of newInstanceIds) {
			await addSubTaskImage(subTask!.id, instanceId);
		}
		for (const instanceId of removedInstanceIds) {
			await removeSubTaskImage(subTask!.id, instanceId);
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
	</div>
	<div id="selection">
		{#each browserContext.selectedInstances as instance (instance.id)}
			<InstanceComponent {instance} />
		{/each}
	</div>
	<div id="content">
		{#await searching}
			<div class="loading-message">Searching for patient images...</div>
		{:then}
			<BrowserContent mode="overlay" />
		{/await}
	</div>
</div>

<style>
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

	/* Override dark theme for all child components */
	div#browser-overlay :global(*) {
		color: #1a1a1a !important;
	}

	div#browser-overlay :global(.bg-gray-200) {
		background-color: #f3f4f6 !important;
	}

	div#browser-overlay :global(.border-gray-300) {
		border-color: #d1d5db !important;
	}

	div#browser-overlay :global(.text-white) {
		color: #1a1a1a !important;
	}

	div#browser-overlay :global(.bg-gray-800) {
		background-color: #f9fafb !important;
	}

	div#browser-overlay :global(.bg-gray-900) {
		background-color: #ffffff !important;
	}
</style>
