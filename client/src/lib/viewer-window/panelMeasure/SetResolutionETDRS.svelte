<script lang="ts">
	import { Button } from '$lib/components/ui/button';
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

<Button variant="outline" size="sm" onclick={() => measureTool.setResolution(val)} class="flex-1 justify-center">
	From {name}
	<br />
	{val.toFixed(2)} μm/pix
</Button>
