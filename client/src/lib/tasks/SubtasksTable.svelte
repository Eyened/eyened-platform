<script lang="ts">
	import { BrowserContext } from "$lib/browser/browserContext.svelte";
	import PaginatedResults from "$lib/components/PaginatedResults.svelte";
	import * as Table from "$lib/components/ui/table";
	import SubTaskRow from "$lib/tasks/SubTaskRow.svelte";
	import { getContext, setContext } from "svelte";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type {
		SubTaskGET,
		SubTaskWithImagesGET,
	} from "../../types/openapi_types";

	type SubTaskAny = SubTaskGET | SubTaskWithImagesGET;

	let {
		rows,
		taskId,
		count,
		page,
		perPage = 20,
		onPageChange,
	}: {
		rows: SubTaskAny[];
		taskId: number;
		count: number;
		page: number;
		perPage?: number;
		onPageChange: (p: number) => void;
	} = $props();

	const globalContext = getContext<GlobalContext>("globalContext");
	const browserContext = new BrowserContext();
	setContext("browserContext", browserContext);

	const start = $derived(page * perPage);
</script>

<PaginatedResults {count} {perPage} {page} {onPageChange}>
	<div class="rounded-md border">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>ID</Table.Head>
					<Table.Head>Status</Table.Head>
					<Table.Head>View</Table.Head>
					<Table.Head>Images</Table.Head>
					<Table.Head>Comments</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each rows as row, index (row.id)}
					<SubTaskRow subtask={row} {taskId} {index} {start} />
				{:else}
					<Table.Row>
						<Table.Cell colspan="5" class="h-24 text-center"
							>No results.</Table.Cell
						>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
</PaginatedResults>
