<script lang="ts">
	import Browser from '$lib/browser/Browser.svelte';

</script>

<svelte:head>
	<title>Eyened browser</title>
</svelte:head>

<Browser />

<style>
	:global(body) {
		margin: 0;
		height: 100vh;
		font-family: Verdana, sans-serif;
		background-color: white;
		color: rgb(99, 99, 99);
	}
	:global(canvas) {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		right: 0;
	}
</style>
