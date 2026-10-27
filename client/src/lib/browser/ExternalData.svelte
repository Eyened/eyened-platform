<script lang="ts">
    import type { DataRow, DataSource } from "$lib/browser/dataSources";
    import { Button } from "$lib/components/ui/button/index.js";
    import { openNewWindow } from "$lib/newWindow";
    import DataTable from "$lib/utils/DataTable.svelte";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";

    let { data }: { data: DataSource } = $props();

    function open(tag: string, rows: DataRow[]) {
        openNewWindow(DataTable, { data: rows }, tag);
    }
</script>

<ul class="flex flex-col items-start">
    {#each Object.entries(data) as [tag, rows] (tag)}
        <li>
            <Button variant="ghost" size="sm" onclick={() => open(tag, rows)}>
                {tag}
                <Launch aria-hidden="true" />
            </Button>
        </li>
    {/each}
</ul>
