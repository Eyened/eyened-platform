<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '2em' }: Props = $props();
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	class="icon icon-tabler icon-tabler-chart-donut-2"
	width={size}
	height={size}
	viewBox="-2 -2 4 4"
	stroke-width="0.5"
	stroke-linecap="round"
	stroke-linejoin="round"
>
	<line x1="-1" y1="-1" x2="1" y2="1" />
	<line x1="1" y1="-1" x2="-1" y2="1" />
</svg>

<style>
	svg {
		fill: none;
		stroke: currentColor;
	}
</style>
