<script lang="ts">
	import MultiSelectWithSearch from "$lib/components/MultiSelectWithSearch.svelte";
	import * as Input from "$lib/components/ui/input";
	import { features } from "$lib/data/stores.svelte";
	import { getContext } from "svelte";
	import type { FeatureGET, FeaturePATCH } from "../../types/openapi_types";
	import { Button } from "$lib/components/ui/button";

	type Props = { feature?: FeatureGET; onsubmit?: (payload: FeaturePATCH) => void };
	let { feature, onsubmit }: Props = $props();

	// Initial-only state, no $effect
	let name = $state(feature ? feature.name : "");
	let description = $state(""); // UI-only unless API adds support
	let subIds = $state<string[]>(
		feature?.subfeature_ids?.map(String) ?? []
	);

	const options = $derived(
		Array.from(features.values())
			.filter(f => f.id !== feature?.id)
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

<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="flex flex-col gap-3">
	<label class="flex flex-col gap-1">
		<span>Name</span>
		<Input.Root type="text" bind:value={name} required />
	</label>

	<label class="flex flex-col gap-1">
		<span>Description</span>
		<textarea bind:value={description} class="border px-2 py-1 rounded" rows="3"></textarea>
	</label>

	<label class="flex flex-col gap-1">
		<span>Subfeatures</span>
		<MultiSelectWithSearch options={options} bind:values={subIds} />
	</label>

	<div class="mt-2">
		<Button type="submit" variant="default">Save</Button>
	</div>
</form>
