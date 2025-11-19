<script lang="ts">
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import { getContext } from "svelte";
	import type {
		ModelSegmentationGET,
		SegmentationGET,
	} from "../../../types/openapi_types";
	import AI from "../icons/AI.svelte";
	import DrawingTools from "./DrawingTools.svelte";
	import NewSegmentation from "./NewSegmentation.svelte";
	import SegmentationItem from "./SegmentationItem.svelte";
	import { groupByCreator } from "./segmentationUtils";
	const globalContext = getContext<GlobalContext>("globalContext");

	interface Props {
		active: boolean;
	}
	let { active }: Props = $props();

	const user_id = globalContext.user.id;

	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");

	// This is used to not render when the panel is collapsed
	// Perhaps there is a cleaner solution?
	$effect(() => {
		mainViewerContext.active = active;
	});

	type SegmentationType = SegmentationGET | ModelSegmentationGET;
	const segmentationContext = mainViewerContext.segmentationContext;

	const segmentationsByCreators = $derived(
		groupByCreator(segmentationContext.graderSegmentations),
	);
</script>

{#snippet creatorSegmentations(segmentations: SegmentationType[])}
	{@const creator = segmentations[0].creator}
	<li
		class="creator"
		class:active={segmentationContext.creatorVisible.has(creator.id)}
	>
		<button
			type="button"
			class="creator-toggle"
			onclick={() => segmentationContext.toggleShowCreator(creator.id)}
			aria-expanded={segmentationContext.creatorVisible.has(creator.id)}
		>
			{segmentationContext.creatorVisible.has(creator.id) ? "▼" : "►"}
			{creator.name}
		</button>

		<div
			class="segmentation-list"
			class:is-hidden={!segmentationContext.creatorVisible.has(creator.id)}
			aria-hidden={!segmentationContext.creatorVisible.has(creator.id)}
		>
			{#each segmentations as segmentation (segmentation.id)}
				<SegmentationItem {segmentation} />
			{/each}
		</div>
	</li>
{/snippet}
<div class="main">
	<div class="opacity">
		<label>
			Opacity:
			<input
				type="range"
				bind:value={mainViewerContext.alpha}
				min="0"
				max="1"
				step="0.01"
			/>
		</label>
	</div>
	<DrawingTools />
	<ul class="users">
		{#if segmentationContext.modelSegmentations.length > 0}
			<li class="creator" class:active={segmentationContext.modelVisible}>
				<button
					type="button"
					class="creator-toggle"
					onclick={() => segmentationContext.toggleShowModel()}
					aria-expanded={segmentationContext.modelVisible}
				>
					{segmentationContext.modelVisible ? "▼" : "►"}
					<AI size="1.2em" />
					<span>AI</span>
				</button>

				<div
					class="segmentation-list"
					class:is-hidden={!segmentationContext.modelVisible}
					aria-hidden={!segmentationContext.modelVisible}
				>
					{#each segmentationContext.modelSegmentations as segmentation}
						<SegmentationItem {segmentation} />
					{/each}
				</div>
			</li>
		{/if}
		<!-- render own segmentations first -->
		{#if segmentationsByCreators.has(user_id)}
			{@const segmentations = segmentationsByCreators.get(user_id)!}
			{@render creatorSegmentations(segmentations)}
		{/if}
		<!-- render other segmentations -->
		{#each segmentationsByCreators.entries() as [creatorId, segmentations]}
			{#if creatorId != user_id}
				{@render creatorSegmentations(segmentations)}
			{/if}
		{/each}
	</ul>
	<NewSegmentation />
</div>

<style>
	div {
		display: flex;
	}

	ul {
		list-style-type: none;
		margin: 0;
	}
	li.active {
		background-color: rgba(255, 255, 255, 0.1);
	}
	div.opacity {
		/* background-color: rgba(255, 255, 255, 0.1); */
		/* border-bottom: 1px solid rgba(255, 255, 255, 0.4); */
		padding: 0.5em;
	}
	div.main {
		flex: 1;
		flex-direction: column;
	}
	li.creator {
		display: flex;
		flex-direction: column;
	}
	div.segmentation-list {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	div.segmentation-list.is-hidden {
		visibility: hidden;
		height: 0;
		overflow: hidden;
		pointer-events: none;
	}
	button.creator-toggle {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.25rem 0.5rem;
		width: 100%;
		border: none;
		background: transparent;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}
	button.creator-toggle:hover {
		background-color: rgba(255, 255, 255, 0.08);
	}
	button.creator-toggle:focus-visible {
		outline: 2px solid currentColor;
		outline-offset: 2px;
	}
	label {
		display: flex;
	}
</style>
