<script lang="ts">
	import type { Creator } from '$lib/datamodel/creator';
	import SegmentationGroup from './SegmentationGroup.svelte';
	import type { Annotation } from '$lib/datamodel/annotation';
	import { getContext } from 'svelte';
	import { SegmentationContext } from './segmentationContext.svelte';

	interface Props {
		creator: Creator;
		annotations: Annotation[];
	}
	let { creator, annotations }: Props = $props();

	const segmentationContext = getContext<SegmentationContext>('segmentationContext');
	const { hideCreators, hideFeatures, hideAnnotations } = segmentationContext;
	function toggle() {
		if (hideCreators.has(creator)) {
			hideCreators.delete(creator);
		} else {
			hideCreators.add(creator);
		}
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<span class="creator-name" onclick={toggle}>
	{hideCreators.has(creator) ? '►' : '▼'}
	{creator.name}
</span>

{#each annotations as annotation (annotation.id)}
	<div
		class="item"
		class:hide={hideFeatures.has(annotation.feature) || hideCreators.has(annotation.creator)}
	>
		<SegmentationGroup {annotation} />
	</div>
{/each}

<style>
	span.creator-name {
		cursor: pointer;
	}
	.creator-name {
		display: flex;
	}
	.creator-name:hover {
		cursor: pointer;
		background-color: rgba(255, 255, 255, 0.1);
	}
	div.item.hide {
		height: 0;
		overflow: hidden;
	}
</style>
