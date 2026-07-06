<script lang="ts">
	import { BrowserContext } from "$lib/browser/browserContext.svelte";
	import PaginatedResults from "$lib/components/PaginatedResults.svelte";
	import * as Table from "$lib/components/ui/table";
	import SubTaskRow from "$lib/tasks/SubTaskRow.svelte";
	import { setContext } from "svelte";
	import type { SubTaskWithImagesGET } from "../../types/openapi_types";

	let {
		rows,
		taskId,
		count,
		page,
		perPage = 20,
		onPageChange,
	}: {
		rows: SubTaskWithImagesGET[];
		taskId: number;
		count: number;
		page: number;
		perPage?: number;
		onPageChange: (p: number) => void;
	} = $props();

	const browserContext = new BrowserContext();
	setContext("browserContext", browserContext);
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
				{#each rows as row (row.id)}
					<SubTaskRow subtask={row} {taskId} />
				{:else}
					<Table.Row>
						<Table.Cell colspan="5" class="h-24 text-center">
							No results.
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
</PaginatedResults>
