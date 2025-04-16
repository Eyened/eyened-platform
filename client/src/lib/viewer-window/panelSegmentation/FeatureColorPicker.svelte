<script lang="ts">
	import { fromHex, toHex } from '$lib/utils';
	import type { SegmentationOverlay } from '$lib/viewer/overlays/SegmentationOverlay.svelte';

	import { getContext } from 'svelte';
	import PanelIcon from '../icons/PanelIcon.svelte';
	import type { Segmentation } from '$lib/webgl/SegmentationController';

	interface Props {
		segmentation: Segmentation;
	}
	let { segmentation }: Props = $props();

	const segmentationOverlay = getContext<SegmentationOverlay>('segmentationOverlay');

	let currentColor = $state('');

	currentColor = toHex(segmentationOverlay.getFeatureColor(segmentation));
	function handleColorChange(e) {
		const newColor = e.target.value;
		segmentationOverlay.setFeatureColor(segmentation, fromHex(newColor));
		currentColor = newColor;
	}
</script>

<PanelIcon tooltip="Change color">
	<label class="tool">
		<i class="color-picker" style="background-color: {currentColor};"></i>
		<input type="color" value={currentColor} oninput={handleColorChange} />
	</label>
</PanelIcon>

<style>
	input {
		visibility: hidden;
		position: absolute;
	}
	i.color-picker {
		cursor: pointer;
		width: 1.2em;
		height: 1.2em;
		margin: 0.1em;
		border-radius: 50%;
		display: flex;
	}
</style>
