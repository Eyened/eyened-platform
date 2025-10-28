<script lang="ts">
  import { createSvelteTable, FlexRender, renderComponent } from "$lib/components/ui/data-table";
  import { Progress } from "$lib/components/ui/progress/index.js";
  import * as Table from "$lib/components/ui/table";
  import type { ColumnDef } from "@tanstack/table-core";
  import { getCoreRowModel } from "@tanstack/table-core";
  import type { TaskGET } from "../../types/openapi_types";
  import TaskActionsCell from "./TaskActionsCell.svelte";
  import TaskNameCell from "./TaskNameCell.svelte";

  let { rows }: { rows: TaskGET[] } = $props();

  const columns: ColumnDef<TaskGET>[] = [
    {
      accessorKey: "name",
      header: "Task",
      cell: ({ row }) => {
        const r = row.original as TaskGET;
        const url = `/tasks/${r.id}${typeof window !== 'undefined' ? window.location.search : ''}`;
        
        return renderComponent(TaskNameCell, { task: r, url });
      }
    },
    {
      accessorKey: "task_state", 
      header: "State",
      cell: ({ row }) => (row.original.task_state ?? "-")
    },
    {
      id: "creator",
      header: "Creator", 
      cell: ({ row }) => (row.original.creator?.name ?? "-")
    },
    {
      id: "progress",
      header: "Progress",
      cell: ({ row }) => {
        const r = row.original;
        const ready = r.num_tasks_ready ?? 0;
        const total = r.num_tasks ?? 0;
        const pct = Math.round(100 * ready / Math.max(1, total));
        
        return renderComponent(Progress, {
          value: pct,
          max: 100,
        });
      }
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => {
        return renderComponent(TaskActionsCell, { 
          task: row.original
        });
      }
    }
  ];

  const table = createSvelteTable({
    get data() { return rows; },
    columns,
    getCoreRowModel: getCoreRowModel()
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
                <FlexRender content={header.column.columnDef.header} context={header.getContext()} />
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
              <FlexRender content={cell.column.columnDef.cell} context={cell.getContext()} />
            </Table.Cell>
          {/each}
        </Table.Row>
      {:else}
        <Table.Row>
          <Table.Cell colspan={columns.length} class="h-24 text-center">No results.</Table.Cell>
        </Table.Row>
      {/each}
    </Table.Body>
  </Table.Root>
</div>
