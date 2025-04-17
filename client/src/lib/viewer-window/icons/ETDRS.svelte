<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '2em' }: Props = $props();

	const d_inner = Math.sqrt(0.5 ** 2 / 2);
	const d_outer = Math.sqrt(3 ** 2 / 2);
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	class="icon icon-tabler icon-tabler-chart-donut-2"
	width={size}
	height={size}
	viewBox="-3.5 -3.5 7 7"
	stroke-width="0.3"
	fill="none"
	stroke-linecap="round"
	stroke-linejoin="round"
>
	<path stroke="none" d="M0 0h24v24H0z" fill="none" />
	<circle cx="0" cy="0" r="0.5" />
	<circle cx="0" cy="0" r="1.5" />
	<circle cx="0" cy="0" r="3" />
	<line x1={-d_outer} y1={-d_outer} x2={-d_inner} y2={-d_inner} />
	<line x1={d_outer} y1={-d_outer} x2={d_inner} y2={-d_inner} />
	<line x1={-d_outer} y1={d_outer} x2={-d_inner} y2={d_inner} />
	<line x1={d_outer} y1={d_outer} x2={d_inner} y2={d_inner} />
</svg>

<style>
	svg {
		fill: none;
		stroke: currentColor;
	}
</style>