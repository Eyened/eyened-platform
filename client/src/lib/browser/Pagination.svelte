
<script lang="ts">
	import * as Pagination from "$lib/components/ui/pagination"
	import type { BrowserContext } from '$lib/data-loading/browserContext'
	import { getContext } from "svelte"

	const browserContext = getContext<BrowserContext>('browserContext');
	const { loading, conditions, page, limit, count, search } = browserContext;

	export let onChange: (page: number) => void;
</script>

<Pagination.Root count={$count} perPage={$limit} onPageChange={onChange} let:pages let:currentPage>
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
</Pagination.Root>
