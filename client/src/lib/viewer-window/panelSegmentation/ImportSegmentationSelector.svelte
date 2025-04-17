<script lang="ts">
	import type { DialogueType } from '$lib/types';
	import type { Segmentation } from '$lib/webgl/SegmentationController';
	
	interface Props {
		availableSegmentations: Segmentation[];
		segmentation: Segmentation;
		dialogue: DialogueType;
	}

	let { availableSegmentations, segmentation, dialogue }: Props = $props();

	let selected: Segmentation | null = $state(null);
	let hover: Segmentation | undefined = $state(undefined);
	function selectRow(segmentation: Segmentation) {
		selected = segmentation;
	}
</script>

<div>Select annotation to import from:</div>
<ul>
	{#each availableSegmentations as currentSegmentation (currentSegmentation.annotation.id)}
		{#if currentSegmentation != segmentation}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
			<li
				onclick={() => selectRow(currentSegmentation)}
				class:selected={currentSegmentation === selected}
				class:hover={currentSegmentation === hover}
				onpointerenter={() => (hover = currentSegmentation)}
				onpointerleave={() => (hover = undefined)}
			>
				<div class="annotation-id">[{currentSegmentation.annotation.id}]</div>
				<div>{currentSegmentation.annotation.creator.name}</div>
				<div>{currentSegmentation.annotation.feature.name}</div>
			</li>
		{/if}
	{/each}
</ul>
<div>
	<button class="approve" onclick={() => dialogue.resolve(selected)} disabled={selected === null}>
		{dialogue.approve}
	</button>
	<button class="decline" onclick={dialogue.reject}>
		{dialogue.decline}
	</button>
</div>

<style>
	ul {
		display: grid;
		grid-template-columns: 0fr 1fr 1fr;

		list-style-type: none;
		padding: 0;
		max-height: 20em;
		overflow: auto;
	}

	li {
		display: contents;
		cursor: pointer;
	}

	div.annotation-id {
		font-size: x-small;
		color: gray;
	}
	li > div {
		padding: 0.5em;
		align-items: center;
		display: flex;
		border-bottom: 1px solid rgba(0, 0, 0, 0.2);
	}
	li.hover > div {
		background-color: #e6fdff;
	}
	li.selected > div {
		background-color: #43ff46;
	}
</style>
