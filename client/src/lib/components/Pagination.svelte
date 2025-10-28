<script lang="ts">
	import * as Pagination from "$lib/components/ui/pagination";

	let {
		count,
		perPage,
		page,
		onPageChange
	}: {
		count: number;
		perPage: number;
		page: number; // 0-based
		onPageChange: (page: number) => void; // 0-based
	} = $props();
</script>

<Pagination.Root
	count={count}
	perPage={perPage}
	page={page + 1}
	onPageChange={(p) => onPageChange(p - 1)}
>
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
