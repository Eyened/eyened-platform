<script lang="ts">
	import Popup from '$lib/Popup.svelte';
	import type { GlobalContext } from '$lib/data-loading/globalContext.svelte.js';
	import { setContext } from 'svelte';

	let { children, data } = $props();
	const globalContext: GlobalContext = data.globalContext;
	setContext('globalContext', globalContext);
	function close() {
		globalContext.popupComponent = null;
	}
</script>

{#if globalContext.popupComponent}
	<Popup componentDef={globalContext.popupComponent} {close} />
{/if}

{@render children()}

<style>
	:global(body) {
		margin: 0;
		height: 100vh;
		font-family: Verdana, sans-serif;
		font-size: small;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}
</style>
