<script lang="ts">
	import * as AlertDialog from '$lib/components/ui/alert-dialog';
	import type { GlobalContext } from '$lib/data/globalContext.svelte';
	import type { FeatureObject } from '$lib/data/objects.svelte';
	import { getContext, onMount } from 'svelte';
	import type { FeaturePATCH, FeaturePUT } from '../../types/openapi_types';
	import FeatureForm from './FeatureForm.svelte';

	const globalContext = getContext<GlobalContext>('globalContext');

	let editing: FeatureObject | null = $state(null);
	let isCreating = $state(false);
	let deletingFeature: FeatureObject | null = $state(null);

	onMount(async () => {
		await globalContext.ensureFeaturesLoaded();
	});

	function startCreate() {
		editing = null;
		isCreating = true;
	}

	function startEdit(feature: FeatureObject) {
		editing = feature;
		isCreating = false;
	}

	function cancelEdit() {
		editing = null;
		isCreating = false;
	}

	async function handleCreate(payload: FeaturePATCH) {
		try {
			await globalContext.features.create({
				name: payload.name!,
				subfeature_ids: payload.subfeature_ids ?? null
			} as FeaturePUT);
			cancelEdit();
		} catch (error) {
			console.error('Failed to create feature:', error);
		}
	}

	async function handleEdit(payload: FeaturePATCH) {
		if (!editing) return;
		try {
			await editing.save(payload);
			cancelEdit();
		} catch (error) {
			console.error('Failed to update feature:', error);
		}
	}

	function handleSubmit(payload: FeaturePATCH) {
		if (isCreating) {
			handleCreate(payload);
		} else {
			handleEdit(payload);
		}
	}

	async function confirmDelete() {
		if (!deletingFeature) return;
		try {
			await deletingFeature.destroy();
			deletingFeature = null;
		} catch (error) {
			console.error('Failed to delete feature:', error);
		}
	}
</script>

<div class="p-4">
	<div class="flex justify-between items-center mb-4">
		<h2 class="text-2xl font-bold">Features</h2>
		<button 
			onclick={startCreate} 
			class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
		>
			Add Feature
		</button>
	</div>

	{#if isCreating || editing}
		<div class="mb-6 p-4 border rounded-lg bg-gray-50">
			<h3 class="text-lg font-semibold mb-3">
				{isCreating ? 'Create Feature' : 'Edit Feature'}
			</h3>
			{#key editing?.id ?? 'new'}
				<FeatureForm feature={editing ?? undefined} onsubmit={handleSubmit} />
			{/key}
			<button 
				onclick={cancelEdit} 
				class="mt-2 bg-gray-500 text-white px-3 py-1 rounded hover:bg-gray-600"
			>
				Cancel
			</button>
		</div>
	{/if}

	<div class="space-y-2">
		{#each globalContext.features.all as featureData (featureData.id)}
			{@const feature = globalContext.features.object(featureData.id)}
			<div class="flex items-center justify-between p-3 border rounded-lg">
				<div class="flex-1">
					<div class="font-medium">{feature.$.name}</div>
					{#if feature.$.subfeatures.length > 0}
						<div class="text-sm text-gray-600">
							Subfeatures: {feature.$.subfeatures.join(', ')}
						</div>
					{/if}
				</div>
				<div class="flex gap-2">
					<button 
						onclick={() => startEdit(feature)} 
						class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
					>
						Edit
					</button>
					<button 
						onclick={() => deletingFeature = feature} 
						class="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700"
					>
						Delete
					</button>
				</div>
			</div>
		{/each}
	</div>

	<AlertDialog.Root open={!!deletingFeature}>
		<AlertDialog.Content>
			<AlertDialog.Header>
				<AlertDialog.Title>Delete Feature</AlertDialog.Title>
				<AlertDialog.Description>
					Are you sure you want to delete "{deletingFeature?.$.name}"? This action cannot be undone.
				</AlertDialog.Description>
			</AlertDialog.Header>
			<AlertDialog.Footer>
				<AlertDialog.Cancel onclick={() => deletingFeature = null}>Cancel</AlertDialog.Cancel>
				<AlertDialog.Action onclick={confirmDelete}>Delete</AlertDialog.Action>
			</AlertDialog.Footer>
		</AlertDialog.Content>
	</AlertDialog.Root>
</div>
