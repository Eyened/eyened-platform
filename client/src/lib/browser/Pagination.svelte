
<script lang="ts">
	import * as Pagination from "$lib/components/ui/pagination";
	import { getContext } from "svelte";
	import type { BrowserContext } from './browserContext.svelte';

	const browserContext = getContext<BrowserContext>('browserContext');

	let { onChange }: { onChange: (page: number) => void } = $props();
</script>


<Pagination.Root count={browserContext.count} perPage={browserContext.limit} page={browserContext.page} onPageChange={onChange}>
	{#snippet children({ pages, currentPage })}
	<Pagination.Content>
		<Pagination.Item>
			<Pagination.PrevButton />
		</Pagination.Item>
		{#each pages as page (page.key)}
		{#if page.type === "ellipsis"}
			<Pagination.Item>
				<Pagination.Ellipsis />
			</Pagination.Item>
		{:else}
			<Pagination.Item isVisible={currentPage == page.value}>
				<Pagination.Link {page} isActive={currentPage == page.value}>
					{page.value}
				</Pagination.Link>
			</Pagination.Item>
		{/if}
		{/each}
		<Pagination.Item>
			<Pagination.NextButton />
		</Pagination.Item>
	</Pagination.Content>
	{/snippet}
</Pagination.Root>