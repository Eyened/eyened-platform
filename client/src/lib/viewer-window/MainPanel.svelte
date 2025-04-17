<script lang="ts">
	import { setContext } from 'svelte';
	import { type MainPanelType, ViewerWindowContext } from './viewerWindowContext.svelte';

	interface Props {
		panel: MainPanelType;
		viewerWindowContext: ViewerWindowContext;
		children?: import('svelte').Snippet;
	}

	let { panel, viewerWindowContext, children }: Props = $props();
	setContext('closePanel', () => viewerWindowContext.removePanel(panel));
</script>

<div id="main">
	{@render children?.()}
</div>

<style>
	div#main {
		display: flex;
		flex: 1;
		position: relative;
	}
</style>
