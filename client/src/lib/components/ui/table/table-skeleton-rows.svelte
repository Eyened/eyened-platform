<script lang="ts">
    import { cn } from "$lib/utils.js";
    import { skeleton } from "./skeleton.js";
    import Cell from "./table-cell.svelte";
    import Row from "./table-row.svelte";

    // Carbon DataTableSkeleton body rows; also shown inside a live table while it reloads.
    let { columns, rowCount = 5 }: { columns: number; rowCount?: number } =
        $props();
</script>

{#each { length: rowCount }, r (r)}
    <Row class="hover:bg-layer-01">
        {#each { length: columns }, c (c)}
            <Cell><span class={cn(skeleton, "h-4 w-16")}></span></Cell>
        {/each}
    </Row>
{/each}
