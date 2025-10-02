<script lang="ts">
	import Pagination from './Pagination.svelte';

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

<div class="flex flex-col flex-1 gap-2">
	<div class="flex justify-center">
		<Pagination {count} {perPage} {page} {onPageChange} />
	</div>

	<div class="flex flex-col flex-1">
		<slot />
	</div>

	<div class="flex justify-center">
		<Pagination {count} {perPage} {page} {onPageChange} />
	</div>
</div>
