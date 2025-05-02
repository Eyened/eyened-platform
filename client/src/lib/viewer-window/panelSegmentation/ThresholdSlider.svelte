<script lang="ts">
	import type { ProbabilitySegmentation } from '$lib/webgl/probabilitySegmentation.svelte';
	import { globalContext } from '$lib/main';

	interface Props {
		segmentation: ProbabilitySegmentation;
	}
	let { segmentation }: Props = $props();

	const annotation = segmentation.annotation;
	const canEditForm = $globalContext.canEdit(annotation);

	function onUpdateThreshold() {
		if (canEditForm) {
			const th = segmentation.threshold;

			// updates the threshold value in the annotation data on server
			for (const ad of annotation.annotationDatas.$) {
				const current = ad.parameters.value || {};
				current.valuefloat = th;
				ad.parameters.setValue(current);
			}
		}
	}
</script>

<label>
	<span>Threshold: {segmentation.threshold}</span>
	<input
		type="range"
		min="0"
		max="1"
		step="0.01"
		bind:value={segmentation.threshold}
		onchange={onUpdateThreshold}
	/>
</label>

<style>
	label {
		display: flex;
		flex-direction: column;
	}
</style>
