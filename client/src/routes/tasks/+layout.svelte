<script lang="ts">
	let { children } = $props();
</script>

{@render children()}

<style>
	:global(body) {
		background-color: Azure;
	}
</style>
