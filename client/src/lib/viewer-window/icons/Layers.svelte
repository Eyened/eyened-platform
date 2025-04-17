<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '2em' }: Props = $props();
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	class="icon icon-tabler icon-tabler-stack-2"
	width={size}
	height={size}
	viewBox="0 0 24 24"
	stroke-width="1.5"
	stroke-linecap="round"
	stroke-linejoin="round"
>
	<path stroke="none" d="M0 0h24v24H0z" fill="none" />
	<polyline points="12 4 4 8 12 12 20 8 12 4" />
	<polyline points="4 12 12 16 20 12" />
	<polyline points="4 16 12 20 20 16" />
</svg>

<style>
	svg {
		fill: none;
		stroke: currentColor;
	}
</style>
