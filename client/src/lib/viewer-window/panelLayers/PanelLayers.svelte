<script lang="ts">
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext, setContext } from 'svelte';
	import CreatorSegmentations from '../panelSegmentation/CreatorSegmentations.svelte';
	import type { Annotation } from '$lib/datamodel/_annotation.svelte';
	import { data } from '$lib/datamodel/model';
	import { SegmentationContext } from '../panelSegmentation/segmentationContext.svelte';

	const viewerContext = getContext<ViewerContext>('viewerContext');

	setContext('viewerContext', viewerContext);

	const { image } = viewerContext;

	const segmentationContext = new SegmentationContext();
	setContext('segmentationContext', segmentationContext);

	const filter = (annotation: Annotation) => {
		const { feature } = annotation;
		if (annotation.instance !== image.instance) return false;

		// TODO: better representation to filter layer segmentation?
		const interpretation = annotation.annotationType.interpretation;
		if (!(interpretation == 'Label numbers' || interpretation == 'Layer bits')) return false;
		if (feature.name == 'Macular layers') return true;
		if (feature.name == 'Optic disc features') return true;

		return false;
	};

	const creatorSegmentations = data.annotations.filter(filter).groupBy((a) => a.creator);

	for (const creator of $creatorSegmentations.keys()) {
		segmentationContext.hideCreators.add(creator);
	}
	
</script>

<div class="main">
	<div>
		<ul class="users">
			{#each $creatorSegmentations as [creator, annotations] (creator.id)}
				<li>
					<CreatorSegmentations {creator} {annotations} />
				</li>
			{/each}
		</ul>
	</div>
</div>

<style>
	div.main {
		padding: 0.5em;
	}
	ul {
		list-style-type: none;
		padding-inline-start: 0em;
		margin: 0;
	}
</style>
