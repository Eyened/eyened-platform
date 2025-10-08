<script lang="ts">
    import { getContext } from 'svelte';
    import type { Series } from '../../types/openapi_types';
    import type { BrowserContext } from './browserContext.svelte';
    import InstanceComponent from './InstanceComponent.svelte';

	interface Props {
		series: Series;
		laterality: 'L' | 'R' | null;
		showSegmentationInfo?: boolean;
	}

	const {InstanceRepo} = getContext<BrowserContext>("browserContext");

	let { series, laterality, showSegmentationInfo = true }: Props = $props();

	const instances = (series.instance_ids ?? []).map((id) => InstanceRepo.store[id]!).filter((instance) => instance && instance.laterality == laterality);
    

</script>

{#if instances.length}
	<div class="series flex flex-col bg-[var(--browser-background)] border border-[var(--browser-border)] rounded-[2px] flex-[0_1_auto] m-[0.1em]">
		<div class="items flex flex-1 flex-row flex-wrap gap-[0.3em]">
			{#each instances as instance}
				<InstanceComponent {instance} {showSegmentationInfo} />
			{/each}
		</div>
	</div>
{/if}

<style>

</style>
