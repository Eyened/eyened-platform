<script lang="ts">
	import { getContext } from 'svelte';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import SegmentationArea from './SegmentationArea.svelte';
	import type { Annotation } from '$lib/datamodel/annotation';
	import type { MeasureTool } from '$lib/viewer/tools/Measure.svelte';
	import { BinarySegmentation } from '$lib/webgl/binarySegmentation.svelte';
	import { ProbabilitySegmentation } from '$lib/webgl/probabilitySegmentation.svelte';
	import type { Creator } from '$lib/datamodel/creator';
	import CreatorAreas from './CreatorAreas.svelte';

	interface Props {
		measureTool: MeasureTool;
	}

	let { measureTool }: Props = $props();

	const viewerContext = getContext<ViewerContext>('viewerContext');
	const { image } = viewerContext;
	const { segmentationAnnotations } = image;

	type row = [Annotation, number, number | undefined];
	let all_areas: Map<Creator, row[]> = $derived.by(() => {
		const areas = new Map<Creator, row[]>();
		for (const annotation of $segmentationAnnotations) {
			if (annotation.annotationType.name !== 'Segmentation 2D') {
				continue;
			}
			const segmentationItem = image.segmentationController.getSegmentationItem(annotation);
			const segmentation = segmentationItem.segmentation;

			if (
				segmentation instanceof BinarySegmentation ||
				segmentation instanceof ProbabilitySegmentation
			) {
				const scanNr = viewerContext.index;
				const area = segmentation.pixelArea.get(scanNr);
				const areamm2 =
					area == undefined
						? undefined
						: (area * measureTool.imageResX * measureTool.imageResY) / 1e6;

				const creator = annotation.creator;
				if (!areas.has(creator)) {
					areas.set(creator, []);
				}
				areas.get(creator)!.push([annotation, scanNr, areamm2]);
			}
		}
		return areas;
	});
</script>

<ul>
	{#each all_areas.entries() as [creator, rows]}
		<li>
			<CreatorAreas {creator} {rows} />
		</li>
	{/each}
</ul>

<style>
	ul {
		list-style-type: none;
		padding-left: 0.5em;
		padding-top: 0.5em;
		margin: 0;
	}
</style>
