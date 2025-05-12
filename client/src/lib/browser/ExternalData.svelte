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
    <h4 onclick={() => (collapse = !collapse)}>
        {#if collapse}►{:else}▼{/if}
        {name}
    </h4>
    <ul class:collapse>
        {#each Object.entries(data) as [tag, rows]}
            <li>
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <span onclick={() => open(tag, rows)}>{tag}</span>
            </li>
        {/each}
    </ul>
</div>

<style>
    h4,
    ul {
        padding: 0;
        margin: 0;
    }
    h4 {
        margin-bottom: 0.2em;
        margin-top: 0.2em;
        padding-left: 0.5em;
        cursor: pointer;
    }
    h4:hover {
        background-color: var(--browser-background);
    }

    ul {
        list-style-type: none;
        margin-left: 1em;
    }
    ul.collapse {
        display: none;
    }
    span {
        cursor: pointer;
        font-family: monospace;
    }
    span:hover {
        text-decoration: underline;
    }
</style>
