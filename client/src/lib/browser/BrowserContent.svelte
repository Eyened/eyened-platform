<script lang="ts">
	import { getContext } from "svelte";
	import PaginatedResults from "../components/PaginatedResults.svelte";
	import type { BrowserContext } from "./browserContext.svelte";
	import InstanceComponent from "./InstanceComponent.svelte";
	import StudyBlock from "./StudyBlock.svelte";

	const browserContext = getContext<BrowserContext>("browserContext");

	// export let renderMode: 'studies' | 'instances' = 'studies';
	let { mode = "full" }: { mode?: "full" | "overlay" } = $props();

	function onPageChange(pageNum: number) {
		browserContext.page = pageNum;
		// Re-run search with whichever mode is active
		browserContext.search();
	}
</script>

{#if browserContext.queryMode === "instances" && browserContext.displayMode === "instance"}
	{#if browserContext.orderedInstances.length > 0}
		<PaginatedResults
			count={browserContext.count}
			perPage={browserContext.limit}
			page={browserContext.page}
			{onPageChange}
		>
			<div class="grid gap-2 grid-cols-[repeat(auto-fill,minmax(8em,1fr))]">
				{#each browserContext.orderedInstances as instance (instance.id)}
					<InstanceComponent {instance} />
				{/each}
			</div>
		</PaginatedResults>
	{:else}
		<div class="flex flex-col flex-1">No results</div>
	{/if}
{:else if browserContext.orderedStudies.length > 0}
	<PaginatedResults
		count={browserContext.count}
		perPage={browserContext.limit}
		page={browserContext.page}
		{onPageChange}
	>
		{#each browserContext.orderedStudies as study (study.id)}
			<StudyBlock study={study} {mode} />
		{/each}
	</PaginatedResults>
{:else}
	<div class="flex flex-col flex-1">No results</div>
{/if}
