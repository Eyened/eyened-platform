<script lang="ts">
	import Pagination from './Pagination.svelte';
	let { onChange }: { onChange: (page: number) => void } = $props();
</script>

<div class="flex flex-col flex-1 gap-2">
	<div class="flex justify-center">
		<Pagination onChange={onChange}/>
	</div>

	<div class="flex flex-col flex-1">
		<slot />
	</div>

	<div class="flex justify-center">
		<Pagination onChange={onChange}/>
	</div>
</div>
