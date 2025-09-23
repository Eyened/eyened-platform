<script lang="ts">
	import MultiSelectWithSearch from "$lib/components/MultiSelectWithSearch.svelte";
	import * as Input from "$lib/components/ui/input";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type { FeatureObject } from "$lib/data/objects.svelte";
	import { getContext } from "svelte";
	import type { FeaturePATCH } from "../../types/openapi_types";

	type Props = { feature?: FeatureObject; onsubmit?: (payload: FeaturePATCH) => void };
	let { feature, onsubmit }: Props = $props();

	const globalContext = getContext<GlobalContext>('globalContext');

	// Initial-only state, no $effect
	let name = $state(feature ? feature.$.name : "");
	let description = $state(""); // UI-only unless API adds support
	let subIds = $state<string[]>(
		// TODO: Use feature.$.subfeature_ids once OpenAPI is regenerated
		[]
	);

	const options = $derived(
		globalContext.features.all
			.filter(f => String(f.id) !== String(feature?.id ?? ""))
			.map(f => ({ label: f.name, value: String(f.id) }))
	);

	function handleSubmit() {
		const payload = {
			name: name.trim() || undefined,
			subfeature_ids: subIds.length ? subIds.map(Number) : undefined,
		} as FeaturePATCH;
		onsubmit?.(payload);
	}
</script>

<form on:submit|preventDefault={handleSubmit} class="flex flex-col gap-3">
	<label class="flex flex-col gap-1">
		<span>Name</span>
		<Input.Root type="text" bind:value={name} required />
	</label>

	<label class="flex flex-col gap-1">
		<span>Description</span>
		<textarea bind:value={description} class="border px-2 py-1 rounded" rows="3" />
	</label>

	<label class="flex flex-col gap-1">
		<span>Subfeatures</span>
		<MultiSelectWithSearch options={options} bind:values={subIds} />
	</label>

	<div class="mt-2">
		<button type="submit" class="bg-blue-600 text-white px-3 py-1 rounded">Save</button>
	</div>
</form>
