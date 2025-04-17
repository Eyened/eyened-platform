<script lang="ts">
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import DoubleRangeSlider from '../DoubleRangeSlider.svelte';
	import Brightness from '../icons/Brightness.svelte';
	import { getContext } from 'svelte';

	const viewerContext = getContext<ViewerContext>('viewerContext');
	const w = {
		get start() {
			return viewerContext.windowLevel.min / 255;
		},
		set start(value) {
			viewerContext.windowLevel.min = value * 255;
		},
		get end() {
			return viewerContext.windowLevel.max / 255;
		},
		set end(value) {
			viewerContext.windowLevel.max = value * 255;
		}
	};
</script>

<div class="container">
	<Brightness size="2em" />
	<div class="slider">
		<DoubleRangeSlider bind:start={w.start} bind:end={w.end} />
	</div>
</div>

<style>
	div.container {
		display: flex;
	}
	div.slider {
		margin: 0em 1em;
		width: 10em;
	}
</style>
