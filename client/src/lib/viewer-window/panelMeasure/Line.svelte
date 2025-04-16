<script lang="ts">
	import { MeasureTool, type Line } from '$lib/viewer/tools/Measure.svelte';
	import { PanelIcon, Trash } from '../icons/icons';
	interface Props {
		line: Line;
		measureTool: MeasureTool;
	}

	let { line, measureTool }: Props = $props();

	const lines = measureTool.lines;
	let distance = $derived(measureTool.getDistance(line));
</script>

{#snippet point(pt: { x: number; y: number })}
	({pt.x.toFixed(0)}, {pt.y.toFixed(0)})
{/snippet}

<li
	onpointerenter={() => measureTool.highlight(line)}
	onpointerleave={() => measureTool.highlight(undefined)}
>
	<div class="text">
		<span>
			{@render point(line.start)} - {@render point(line.end)}
		</span>
		<span>
			{distance}
		</span>
	</div>
	<div>
		<PanelIcon onclick={() => lines.delete(line)}>
			<Trash />
		</PanelIcon>
	</div>
</li>

<style>
	li {
		display: flex;
		align-items: center;
		background-color: rgba(255, 255, 255, 0.1);
		padding-left: 0.5em;
		margin-bottom: 0.5em;
		border-radius: 5px;
	}
	li:hover {
		background-color: rgba(255, 255, 255, 0.2);
	}
	span {
		font-size: x-small;
		flex: 1;
	}
	li div.text {
		flex: 1;
	}
	span {
		display: block;
	}
</style>
