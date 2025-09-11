<script lang="ts">
    import { getContext } from 'svelte'
    import type { components } from '../../types/openapi'
    import type { BrowserContext } from './browserContext.svelte'
    import InstanceComponent from './InstanceComponent.svelte'
	type Series = components['schemas']['SeriesGET'];

	interface Props {
		series: Series;
		laterality: 'L' | 'R' | null;
		showSegmentationInfo?: boolean;
	}

	const {InstanceRepo} = getContext<BrowserContext>("browserContext");

	let { series, laterality, showSegmentationInfo = true }: Props = $props();

	const instances = (series.instance_ids ?? []).map((id) => InstanceRepo.store[id]!);
    

</script>

{#if instances.length}
	<div class="series">
		<div class="items">
			{#each instances as instance}
				<InstanceComponent {instance} {showSegmentationInfo} />
			{/each}
		</div>
	</div>
{/if}

<style>
	div {
		display: flex;
	}
	.series {
		flex-direction: column;
		background-color: var(--browser-background);
		border: 1px solid var(--browser-border);
		border-radius: 2px;
		flex: 0 1 auto;
		margin: 0.1em;
	}
	.items {
		display: flex;
		flex: 1;
		flex-direction: row;
		flex-wrap: wrap;
		gap: 0.3em;
	}
</style>
