<script lang="ts">
	import { SetBrushRadiusTool } from '$lib/viewer/tools/setBrushRadius';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';

	import { getContext, onDestroy } from 'svelte';
	import { SegmentationContext } from './segmentationContext.svelte';

	interface Props {
		segmentationContext: SegmentationContext;
	}
	let { segmentationContext }: Props = $props();
	const viewerContext = getContext<ViewerContext>('viewerContext');

	const brushMin = Math.log(0.4);
	const brushMax = Math.log(1000);

	const radiusLog = {
		get value() {
			return Math.log(segmentationContext.brushRadius);
		},
		set value(value: number) {
			segmentationContext.brushRadius = Math.exp(value);
		}
	};

	const tool = new SetBrushRadiusTool(viewerContext, segmentationContext);
	onDestroy(viewerContext.addOverlay(tool));
</script>

<div id="brush-size">
	<div>Brush size: {segmentationContext.brushRadius.toFixed(2)}</div>
	<input type="range" bind:value={radiusLog.value} min={brushMin} max={brushMax} step="0.01" />
</div>

<style>
	div {
		display: flex;
	}
	div#brush-size {
		flex-direction: column;
	}
</style>
