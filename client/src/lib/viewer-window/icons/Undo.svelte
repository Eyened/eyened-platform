<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '3em' }: Props = $props();
</script>

<svg width={size} height={size} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
	<path
		d="M4 7H15C17.7614 7 20 9.23857 20 12C20 14.7614 17.7614 17 15 17H8.00001M4 7L7 4M4 7L7 10"
		stroke-width="1.5"
		stroke-linecap="round"
		stroke-linejoin="round"
	/>
</svg>

<style>
	svg {
		fill: none;
		stroke: currentColor;
	}
</style>
