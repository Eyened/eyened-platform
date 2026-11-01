<script lang="ts">
    import type { DataRow } from "$lib/browser/dataSources";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import * as Table from "$lib/components/ui/table/index.js";

    // A data source's rows have no header row, so the table has no column headers.
    let { data, tag }: { data: DataRow[]; tag: string } = $props();
</script>

<div class="overflow-auto p-4">
    {#if data.length > 0}
        <Table.Root size="md">
            <Table.Caption
                class="mt-0 caption-top bg-layer-01 px-4 pt-4 pb-6 text-left text-heading-03 text-text-primary"
            >
                {tag}
            </Table.Caption>
            <Table.Body>
                {#each data as row, r (r)}
                    <Table.Row>
                        {#each row as cell, c (c)}
                            <Table.Cell>{cell ?? ""}</Table.Cell>
                        {/each}
                    </Table.Row>
                {/each}
            </Table.Body>
        </Table.Root>
    {:else}
        <Empty.Root>
            <Empty.Header>
                <Empty.Title>No data in {tag}</Empty.Title>
                <Empty.Description>
                    The data source returned no rows.
                </Empty.Description>
            </Empty.Header>
        </Empty.Root>
    {/if}
</div>
