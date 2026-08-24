<script lang="ts">
	import {
		createSvelteTable,
		FlexRender,
		renderComponent,
	} from "$lib/components/ui/data-table";
	import * as Table from "$lib/components/ui/table";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { features } from "$lib/data/stores.svelte";
	import {
		getCoreRowModel,
		getSortedRowModel,
		type ColumnDef,
		type SortingState,
	} from "@tanstack/table-core";
	import { createRawSnippet, getContext } from "svelte";
	import type { FeatureGET } from "../../types/openapi_types";
	import FeatureRow from "./FeatureRow.svelte";
	import SortHeader from "./SortHeader.svelte";
	import Button from "./ui/button/button.svelte";

	const globalContext = getContext<GlobalContext>("globalContext");

	let sorting = $state<SortingState>([]);


	const columns: ColumnDef<FeatureGET>[] = [
		{
			accessorKey: "name",
			header: ({ column }) => {
				const onclick = column.getToggleSortingHandler() ?? (() => {});
				return renderComponent(SortHeader, { label: "Feature", onclick });
			},
			cell: ({ row }) => row.original.name ?? "-",
		},
		{
			id: "count",
			accessorFn: () => 0,
			header: ({ column }) => {
				const onclick = column.getToggleSortingHandler() ?? (() => {});
				return renderComponent(SortHeader, { label: "Count", onclick });
			},
			cell: ({ row }) => row.original.segmentation_count ?? "-",
		},
		{
			id: "browser",
			header: "Browser",
			cell: ({ row }) => {
				const children = createRawSnippet(() => ({
					render: () => "Open in Browser",
				}));
				return renderComponent(Button, {
					children,
					class: "button-xs",
					size: "sm",
					variant: "link",
					href: globalContext.makeInstancesBrowserURL({
						variable: "Segmentation Feature Name",
						type: "default",
						operator: "IN",
						value: [row.original.name],
					}),
				});
			},
		},
		{
			id: "actions",
			header: "",
			cell: ({ row }) => {
				return renderComponent(FeatureRow, { feature: row.original });
			},
		},
	];

	const table = createSvelteTable({
		get data() {
			return Array.from(features.values());
		},
		columns,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		onSortingChange: (updater) =>
			(sorting = typeof updater === "function" ? updater(sorting) : updater),
		state: {
			get sorting() {
				return sorting;
			},
		},
	});
</script>

<div class="rounded-md border">
	<Table.Root>
		<Table.Header>
			{#each table.getHeaderGroups() as headerGroup (headerGroup.id)}
				<Table.Row>
					{#each headerGroup.headers as header (header.id)}
						<Table.Head colspan={header.colSpan}>
							{#if !header.isPlaceholder}
								<FlexRender
									content={header.column.columnDef.header}
									context={header.getContext()}
								/>
							{/if}
						</Table.Head>
					{/each}
				</Table.Row>
			{/each}
		</Table.Header>
		<Table.Body>
			{#each table.getRowModel().rows as row (row.id)}
				<Table.Row>
					{#each row.getVisibleCells() as cell (cell.id)}
						<Table.Cell>
							<FlexRender
								content={cell.column.columnDef.cell}
								context={cell.getContext()}
							/>
						</Table.Cell>
					{/each}
				</Table.Row>
			{:else}
				<Table.Row>
					<Table.Cell colspan={columns.length} class="h-24 text-center"
						>No results.</Table.Cell
					>
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
