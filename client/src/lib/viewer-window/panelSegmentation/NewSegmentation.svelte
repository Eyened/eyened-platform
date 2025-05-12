<script lang="ts">
	import { getContext } from 'svelte';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import type { DialogueType } from '$lib/types';
	import type { Writable } from 'svelte/store';
	import FeatureSelect from './FeatureSelect.svelte';
	import { data } from '$lib/datamodel/model';
	import type { Feature } from '$lib/datamodel/feature';
	import { createAnnotation } from '$lib/datamodel/annotation';
	import { featureSetColorFundus, featureSetOCT } from '$lib/viewer-config';
	import { SegmentationContext } from './segmentationContext.svelte';
	import { globalContext } from '$lib/main';

	const { creator } = globalContext;
	const { image } = getContext<ViewerContext>('viewerContext');
	const segmentationContext = getContext<SegmentationContext>('segmentationContext');
	const { annotationTypes, features } = data;

	function getAnnotationType() {
		let annotationTypeName: string;
		if (image.is3D) annotationTypeName = 'Segmentation OCT B-scan';
		else if (image.image_id.endsWith('proj')) annotationTypeName = 'Segmentation OCT Enface';
		else annotationTypeName = 'Segmentation 2D';

		return annotationTypes.find(
			(t) => t.name == annotationTypeName && t.interpretation == 'R/G mask'
		)!;
	}

	const dialogue = getContext<Writable<DialogueType>>('dialogue');

	let selectedFeature: Feature | undefined = $state(undefined);

	async function create(feature: Feature) {
		dialogue.set(`Creating annotation...`);
		const annotation = await createAnnotation(
			image.instance,
			feature,
			creator,
			getAnnotationType()
		);
		segmentationContext.hideCreators.delete(creator);
		dialogue.set(undefined);
	}

	let selectList: { [name: string]: Feature[] } = $state({});
	function selectFeatures(featureSet: { [name: string]: string[] }) {
		for (const [groupname, featurenames] of Object.entries(featureSet)) {
			selectList[groupname] = [];
			for (const name of featurenames) {
				const feature = features.find((f) => f.name == name);
				if (feature) {
					selectList[groupname].push(feature);
				}
			}
		}
	}
	if (image.is3D) {
		selectFeatures(featureSetOCT);
	} else {
		selectFeatures(featureSetColorFundus);
	}
	const availableFeatures = features.filter((f) => {
		// TODO: filter features that are not available for the current image?
		return true;
	}).$;
</script>

<div class="new">
	<div>
		<select bind:value={selectedFeature}>
			<option value="" selected disabled hidden>Select feature:</option>
			{#each Object.entries(selectList) as [groupname, features]}
				<optgroup label={groupname}>
					{#each features as feature}
						<option value={feature}>{feature.name}</option>
					{/each}
				</optgroup>
			{/each}
		</select>
		<button onclick={() => create(selectedFeature!)} disabled={selectedFeature == undefined}>
			Create
		</button>
	</div>
	<FeatureSelect values={availableFeatures} onselect={(feature) => create(feature)} />
</div>

<style>
	div {
		display: flex;
	}
	div.new {
		flex-direction: column;
	}
	select {
		width: 10em;
	}
</style>
