<script lang="ts">
	import type { ETDRSCoordinates } from '$lib/types';
	import type { MeasureTool } from '$lib/viewer/tools/Measure.svelte';

	interface Props {
		value?: ETDRSCoordinates;
		valueFixed?: number;
		measureTool: MeasureTool;
		fraction: number;
		name: string;
	}
	let { value, valueFixed, measureTool, fraction, name }: Props = $props();

	let val = $derived.by(() => {
		if (valueFixed) {
			return valueFixed;
		}
		const { x: fx, y: fy } = value?.fovea || { x: 0, y: 0 };
		const { x: dx, y: dy } = value?.disc_edge || { x: 0, y: 0 };
		const dist = Math.sqrt((fx - dx) ** 2 + (fy - dy) ** 2);

		return 3000 / fraction / dist;
	});
</script>

<button onclick={() => measureTool.setResolution(val)}>
	From {name}
	<br />
	{val.toFixed(2)} μm/pix
</button>

<style>
	button {
		display: flex;
		flex: 1;
		border-radius: 2px;
		background-color: rgba(0, 0, 0, 0.1);
		color: rgba(255, 255, 255, 0.5);
		justify-content: center;
	}
</style>
