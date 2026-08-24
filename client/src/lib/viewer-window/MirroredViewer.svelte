<script lang="ts">
	import Viewer from '$lib/viewer/Viewer.svelte';
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { setContext } from 'svelte';

	interface Props {
		viewerContext: ViewerContext;
	}

	let { viewerContext }: Props = $props();

	setContext('viewerContext', viewerContext);
</script>

<Viewer />
