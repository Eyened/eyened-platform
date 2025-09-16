<script lang="ts">
    import { openNewWindow } from "$lib/newWindow";
    import type { DataRow, DataSource } from "$lib/utils/cached_source_loader";
    import DataTable from "$lib/utils/DataTable.svelte";
    interface Props {
        data: DataSource;
        name: string;
        collapse?: boolean;
    }
    let { data, name, collapse = $bindable(false) }: Props = $props();

    function open(tag: string, rows: DataRow[]) {
        openNewWindow(DataTable, { data: rows }, tag);
    }
</script>

<div>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <h4 class="mb-[0.2em] mt-[0.2em] pl-2 cursor-pointer hover:bg-[var(--browser-background)]" onclick={() => (collapse = !collapse)}>
        {#if collapse}►{:else}▼{/if}
        {name}
    </h4>
    <ul class:hidden={collapse} class="list-none ml-4 p-0 m-0">
        {#each Object.entries(data) as [tag, rows]}
            <li>
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <span class="cursor-pointer font-mono hover:underline" onclick={() => open(tag, rows)}>{tag}</span>
            </li>
        {/each}
    </ul>
</div>

<style>

</style>
