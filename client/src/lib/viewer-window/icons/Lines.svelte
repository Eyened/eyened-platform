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
	viewBox="0 0 5 5"
	stroke-width="0.3"
	fill="none"
	stroke-linecap="round"
	stroke-linejoin="round"
>
	<line x1=0 y1=0 x2=5 y2=0 />
	<line x1=0 y1=1 x2=5 y2=1 />
	<line x1=0 y1=2 x2=5 y2=2 />
	<line x1=0 y1=3 x2=5 y2=3 />
	<line x1=0 y1=4 x2=5 y2=4 />
	
	
</svg>

<style>
	svg {
		fill: none;
		stroke: currentColor;
	}
</style>