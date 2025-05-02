<script lang="ts">
	import type { AbstractImage } from '$lib/webgl/abstractImage';
	import { getContext, onDestroy, onMount } from 'svelte';
	import type { ViewerWindowContext } from '../viewerWindowContext.svelte';
	import { LayerThicknessEnfaceOverlay } from '$lib/viewer/overlays/LayerThicknessEnface';
	import type {
		MulticlassSegmentation,
		MultilabelSegmentation
	} from '$lib/webgl/layerSegmentation';
	import { layerThicknesses, macularLayers } from '../panelSegmentation/segmentationUtils';

	interface Props {
		image: AbstractImage;
		segmentation: MulticlassSegmentation | MultilabelSegmentation;
	}

	let { image, segmentation }: Props = $props();
	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');

	async function getEnface() {
		const images = await viewerWindowContext.getImages(image.instance.id);
		for (const image of images) {
			if (image.depth == 1) {
				return image;
			}
		}
	}
	let enfaceImage: AbstractImage | undefined = $state(undefined);
	let showEnface: undefined | keyof typeof macularLayers = $state(undefined);

	onMount(async () => {
		// find enface for this OCT
		enfaceImage = await getEnface();
	});

	let unsubscribe = () => {};

	$effect(() => {
		if (enfaceImage && showEnface != undefined) {
			unsubscribe();
			const overlay = new LayerThicknessEnfaceOverlay(
				image,
				segmentation,
				macularLayers[showEnface],
				layerThicknesses[showEnface]
			);
			const topViewer = viewerWindowContext.topViewers.get(enfaceImage);
			if (topViewer) {
				unsubscribe = topViewer?.addOverlay(overlay);
			}
		}
	});

	onDestroy(() => unsubscribe());
</script>

{#if enfaceImage}
	<div>
		Show thickness enface:
		<select bind:value={showEnface}>
			<option value={undefined}>None</option>
			{#each Object.keys(macularLayers) as layer}
				{#if layer != 'background'}
					<option value={layer}>{layer}</option>
				{/if}
			{/each}
		</select>
	</div>
{/if}

<style>
	div {
		display: flex;
		flex-direction: column;
		margin-left: 0.2em;
	}
</style>
