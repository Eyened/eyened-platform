<script lang="ts">
	import { getContext } from 'svelte';
	import type { Annotation } from '$lib/datamodel/annotation.svelte';
	import { Registration } from '../../registration/registration';
	import { ViewerContext } from '$lib/viewer/viewerContext.svelte';

	import type { SegmentationContext } from './segmentationContext.svelte';
	import type { Segmentation } from '$lib/webgl/SegmentationController';

	interface Props {
		annotation: Annotation;
		segmentation: Segmentation;
	}

	let { annotation, segmentation }: Props = $props();

	const { annotationData } = annotation;
	const segmentationContext = getContext<SegmentationContext>('segmentationContext');
	const viewerContext = getContext<ViewerContext>('viewerContext');
    const registration = viewerContext.registration;

	async function activateScanNr(e: MouseEvent, scanNr: number) {
		e.stopPropagation();
		// override the lockScroll while setting the position
		const lock = viewerContext.lockScroll;
		viewerContext.lockScroll = false;
		registration.setPosition(segmentation.image.image_id, { x: 0, y: 0, index: scanNr });
		setTimeout(() => (viewerContext.lockScroll = lock), 0);
		segmentationContext.activeAnnotation = segmentation;
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="row links">
	{#each $annotationData as a, i (a.scanNr)}
		{#if i > 0}|{/if}
		<span
			class="link-scan"
			class:active={a.scanNr == viewerContext.index}
			onclick={(e) => activateScanNr(e, a.scanNr)}
		>
			{a.scanNr}
		</span>
	{/each}
</div>

<style>
	div.row {
		flex-direction: row;
		flex: 1;
		width: 100%;
	}
	div.links {
		font-size: x-small;
	}
	.link-scan {
		padding: 0 0.4em;
		cursor: pointer;
	}
	.link-scan.active {
		text-decoration: underline;
	}
	.link-scan:hover {
		color: white;
	}
</style>
