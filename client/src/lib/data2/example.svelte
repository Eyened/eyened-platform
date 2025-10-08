<script lang="ts">
/**
 * Example component demonstrating the new data2 implementation
 * Compare this with components using the old /lib/data/ approach
 */

import { GlobalContext } from './globalContext.svelte';

// Create a global context instance
const gc = new GlobalContext();

// You would normally initialize this in your root layout
// await gc.init(pathname);

// ===== EXAMPLE 1: Fetching and displaying data =====

async function loadInstances() {
	await gc.instances.fetchAll();
}

// Reactive filtering - no need for special stores or subscriptions
const leftInstances = $derived(
	gc.instances.all.filter(i => i.laterality === 'L')
);

const rightInstances = $derived(
	gc.instances.all.filter(i => i.laterality === 'R')
);

// ===== EXAMPLE 2: Working with specific items =====

let selectedInstanceId = $state<number | undefined>(undefined);

const selectedInstance = $derived(
	selectedInstanceId ? gc.instances.get(selectedInstanceId) : undefined
);

async function tagInstance(instanceId: number, tagId: number) {
	const instance = gc.instances.get(instanceId);
	if (!instance) return;
	
	// Call method directly on the instance
	await instance.tag(tagId);
	// UI updates automatically because instance is reactive!
}

// ===== EXAMPLE 3: Traversing relationships =====

// With the old implementation you might do:
// const study = repo.object(instance.$.study_id)
// const description = study.$.description

// With the new implementation:
function getStudyDescription(instanceId: number) {
	const instance = gc.instances.get(instanceId);
	// Direct property access, clean relationship traversal
	return instance?.study?.description;
}

// ===== EXAMPLE 4: Creating new items =====

async function createTag() {
	const tag = await gc.tags.create({
		name: 'Important Finding',
		tag_type: 'ImageInstance',
		description: 'Marks important findings'
	});
	
	// Tag is now in the repo and reactive
	console.log('Created tag:', tag.name);
	await tag.star();
}

// ===== EXAMPLE 5: Optimistic updates =====

async function starTagOptimistic(tagId: number) {
	const tag = gc.tags.get(tagId);
	if (!tag) return;
	
	// Could optimistically update local state first
	// (though tag.star() doesn't return new state in this example)
	try {
		await tag.star();
		// Success - could update local state here
	} catch (error) {
		// Error - could revert local state
		console.error('Failed to star tag:', error);
	}
}

// ===== EXAMPLE 6: Derived collections =====

const studyTags = $derived(
	gc.tags.all.filter(t => t.tagType === 'Study')
);

const instanceTagsByName = $derived(
	gc.tags.all
		.filter(t => t.tagType === 'ImageInstance')
		.sort((a, b) => a.name.localeCompare(b.name))
);

</script>

<div class="examples">
	<h1>Data2 Implementation Examples</h1>
	
	<section>
		<h2>Left Eye Instances</h2>
		<p>Count: {leftInstances.length}</p>
		{#each leftInstances as instance (instance.id)}
			<div class="instance-card">
				<!-- Direct property access - no .$ needed! -->
				<div>ID: {instance.id}</div>
				<div>Modality: {instance.modality}</div>
				<div>Laterality: {instance.laterality}</div>
				
				<!-- Traverse relationships easily -->
				<div>Study: {instance.study?.description ?? 'N/A'}</div>
				<div>Study Date: {instance.study?.date ?? 'N/A'}</div>
				
				<!-- Access nested data -->
				<div>
					Tags: 
					{#each instance.tags as tag}
						<span class="tag">{tag.name}</span>
					{/each}
				</div>
				
				<!-- Call methods -->
				<button onclick={() => tagInstance(Number(instance.id), 1)}>
					Tag this instance
				</button>
			</div>
		{/each}
	</section>
	
	<section>
		<h2>Selected Instance Details</h2>
		{#if selectedInstance}
			<div>
				<h3>{selectedInstance.modality}</h3>
				<p>Dataset ID: {selectedInstance.datasetIdentifier}</p>
				<p>SOP Instance UID: {selectedInstance.sopInstanceUid}</p>
				<p>Dimensions: {selectedInstance.columns} × {selectedInstance.rows}</p>
				
				<!-- Series info -->
				{#if selectedInstance.series}
					<div>
						<h4>Series</h4>
						<p>Series Number: {selectedInstance.series.seriesNumber}</p>
						<p>UID: {selectedInstance.series.seriesInstanceUid}</p>
					</div>
				{/if}
				
				<!-- Segmentations -->
				<div>
					<h4>Segmentations</h4>
					{#each selectedInstance.segmentations as seg}
						<div>{seg.featureName} - {seg.annotationType}</div>
					{/each}
				</div>
			</div>
		{:else}
			<p>No instance selected</p>
		{/if}
	</section>
	
	<section>
		<h2>Tags</h2>
		<div>
			<h3>Study Tags ({studyTags.length})</h3>
			{#each studyTags as tag (tag.id)}
				<div class="tag-item">
					{tag.name} - {tag.description}
					<button onclick={() => tag.star()}>Star</button>
				</div>
			{/each}
		</div>
		
		<div>
			<h3>Instance Tags ({instanceTagsByName.length})</h3>
			{#each instanceTagsByName as tag (tag.id)}
				<div class="tag-item">
					{tag.name}
				</div>
			{/each}
		</div>
		
		<button onclick={createTag}>Create New Tag</button>
	</section>
</div>

<style>
	.examples {
		padding: 2rem;
		max-width: 1200px;
		margin: 0 auto;
	}
	
	section {
		margin: 2rem 0;
		padding: 1rem;
		border: 1px solid #ddd;
		border-radius: 4px;
	}
	
	.instance-card {
		padding: 1rem;
		margin: 0.5rem 0;
		background: #f5f5f5;
		border-radius: 4px;
	}
	
	.tag {
		display: inline-block;
		padding: 0.25rem 0.5rem;
		margin: 0.25rem;
		background: #e0e0e0;
		border-radius: 3px;
		font-size: 0.875rem;
	}
	
	.tag-item {
		padding: 0.5rem;
		margin: 0.25rem 0;
		background: #fafafa;
		border-radius: 3px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	
	button {
		padding: 0.5rem 1rem;
		background: #007bff;
		color: white;
		border: none;
		border-radius: 4px;
		cursor: pointer;
	}
	
	button:hover {
		background: #0056b3;
	}
</style>

