<script lang="ts">
    import { browser } from "$app/environment";
    import { page } from "$app/state";
    import { toggleParam } from "./searchUtils";

    interface Props {
        variable: string; // api variable name (e.g. 'FeatureName')
        values: any[];
        name: string; // name of the value in the data model (e.g. 'name' => feature.name)
    }

    let { variable, values, name }: Props = $props();

    let filter = $state("");
    let filteredValues = $derived.by(() => {
        if (filter) {
            const f = filter.toLowerCase();
            return values.filter((v) => v[name].toLowerCase().includes(f));
        }
        return [];
    });

    let selectedValues: string[] = $state([]);
    if (browser) {
        selectedValues = page.url.searchParams.getAll(variable);
    }

    function toggle(value: string) {
        if (browser) {
            toggleParam(page.url.searchParams, variable, value);
            selectedValues = page.url.searchParams.getAll(variable);
        }
    }
</script>

<input type="text" placeholder="Filter..." bind:value={filter} />
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<ul>
    {#each values as value}
        <li
            class="item"
            onclick={() => toggle(value[name])}
            class:highlight={filter == "" || filteredValues.includes(value)}
            class:active={selectedValues.includes(value[name])}
        >
            {value[name]}
        </li>
    {/each}
</ul>

<style>
    ul {
        display: flex;
        flex-wrap: wrap;
        padding: 0;
        margin: 0;
        list-style-type: none;
    }
    li.item {
        font-size: 0.9em;
        color: rgba(0, 0, 0, 0.6);
        cursor: pointer;
        padding: 0.1em 0.2em;
        margin: 0.1em;
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 0.2em;
        opacity: 0.2;
    }
    li.item:hover {
        background-color: #f1f1f1;
    }
    li.item.active {
        background-color: #b6ddf9;
    }
    li.item.highlight {
        opacity: 1;
    }
</style>
