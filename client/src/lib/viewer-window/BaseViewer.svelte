<script lang="ts">
	import Viewer from '$lib/viewer/Viewer.svelte';
	import { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import type { AbstractImage } from '$lib/webgl/abstractImage';
	import { getContext, setContext } from 'svelte';
	import { ViewerWindowContext } from './viewerWindowContext.svelte';

	interface Props {
		image: AbstractImage;
	}

	let { image }: Props = $props();
	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');
	const viewerContext = new ViewerContext(image, viewerWindowContext);
	setContext('viewerContext', viewerContext);
</script>

<Viewer />
