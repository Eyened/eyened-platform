<script lang="ts">
	import { instances } from '$lib/data';
	import Viewer from '$lib/viewer/Viewer.svelte';
	import { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { AbstractImage } from '$lib/webgl/abstractImage';
	import { Image2D } from '$lib/webgl/image2D';
	import type { ImageRenderer } from '$lib/webgl/imageRenderer';
	import { MultiImageRenderer } from '$lib/webgl/multiImageRenderer';
	import { getContext, setContext } from 'svelte';
	import { ViewerWindowContext } from './viewerWindowContext.svelte';

	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');
	interface Props {
		image: Image2D;
	}

	let { image }: Props = $props();
	// instances is already imported from $lib/data
	const renderer = new MultiImageRenderer(image, viewerWindowContext.registration);
	class MultiViewerContext extends ViewerContext {
		constructor(image: AbstractImage, viewerWindowContext: ViewerWindowContext) {
			super(image, viewerWindowContext);
		}
		getImageRenderer(): ImageRenderer {
			return renderer;
		}
	}

	const viewerContext = new MultiViewerContext(image, viewerWindowContext);
	setContext('viewerContext', viewerContext);

	const CFInstances = instances.filter((i) => i.modality === 'ColorFundus');
	let selectedInstance = CFInstances.first();
	function handleSelectChange(event) {
		const image_id = event.target.value;
		if (selectedInstance) {
			viewerWindowContext.getImages(Number(image_id)).then((loadedImage) => {
				renderer.setImage(loadedImage[0] as Image2D);
			});
		}
	}
	function handleSliderChange(event) {
		renderer.blend = event.target.value;
	}
</script>

<div class="viewer">
	<Viewer />
	<div class="controls">
		<select oninput={handleSelectChange}>
			{#each $CFInstances as instance}
				<option value={instance.id}>{instance.id}</option>
			{/each}
		</select>
		<input type="range" min="0" max="1" step="0.01" value="0.5" oninput={handleSliderChange} />
	</div>
</div>

<style>
	div {
		display: flex;
		flex: 1;
		user-select: none;
	}
	div.viewer {
		flex-direction: row;
	}
	div.controls {
		pointer-events: auto;
	}
</style>
