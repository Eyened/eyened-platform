<script lang="ts">
	import { getContext } from 'svelte';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import type { MeasureTool } from '$lib/viewer/tools/Measure.svelte';
	import type { Creator } from '$lib/datamodel/creator.svelte';
	import CreatorAreas from './CreatorAreas.svelte';
    import { BinaryMask, ProbabilityMask } from '$lib/webgl/Mask';
    import { GlobalContext } from '$lib/data-loading/globalContext.svelte';
    import type { Segmentation } from '$lib/datamodel/segmentation.svelte';

	interface Props {
		measureTool: MeasureTool;
	}

	let { measureTool }: Props = $props();

	const viewerContext = getContext<ViewerContext>('viewerContext');
	const { image } = viewerContext;
	const globalContext = getContext<GlobalContext>('globalContext');
	const segmentations = image.instance.segmentations.filter(globalContext.segmentationsFilter);

	type row = [Segmentation, number, number | undefined];
	let all_areas: Map<Creator, row[]> = $derived.by(() => {
		const areas = new Map<Creator, row[]>();
		for (const segmentation of $segmentations) {
			if (segmentation.feature.name !== 'Segmentation 2D') {
				continue;
			}
			
            const segmentationItem = image.getSegmentationItem(segmentation);
			const segmentationData = segmentationItem.getMask(viewerContext.index);

			if (
				segmentationData instanceof BinaryMask ||
				segmentationData instanceof ProbabilityMask
			) {
				const scanNr = viewerContext.index;
				// const area = segmentation.pixelArea.get(scanNr);
                // TODO: implement pixelArea
                const area = 0;
				const areamm2 =
					area == undefined
						? undefined
						: (area * measureTool.imageResX * measureTool.imageResY) / 1e6;

				const creator = segmentation.creator;
				if (!areas.has(creator)) {
					areas.set(creator, []);
				}
				areas.get(creator)!.push([segmentation, scanNr, areamm2]);
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
