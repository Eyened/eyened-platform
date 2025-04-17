<script lang="ts">
	import { Hide, Show } from './icons';

	let { show = $bindable(true) } = $props();
</script>

{#if show}
	<Show />
{:else}
	<Hide />
{/if}
