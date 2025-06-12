<script lang="ts">
	import type { Feature } from '$lib/datamodel/feature.svelte';
	import { getContext } from 'svelte';
	import { ViewerWindowContext } from '../viewerWindowContext.svelte';
	import { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import type { Annotation } from '$lib/datamodel/annotation.svelte';
	import { FilterList } from '$lib/datamodel/itemList';

	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');
	const { image } = getContext<ViewerContext>('viewerContext');

	interface Props {
		annotations: FilterList<Annotation>;
	}

	let { annotations }: Props = $props();
	const features = annotations.collectSet((a) => a.feature);

	let focusFeature: Feature | undefined = $state(undefined);
	
	viewerWindowContext.setViewFeature(focusFeature, image);
	
</script>

<div class="features">
	<div>
		Focus feature:
		<select bind:value={focusFeature}>
			<option value={undefined}>[Show all]</option>
			{#each $features as feature}
				<option value={feature}>
					{feature.name}
				</option>
			{/each}
		</select>
	</div>
</div>
