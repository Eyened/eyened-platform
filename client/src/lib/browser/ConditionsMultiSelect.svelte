<script lang="ts">
    import { page } from "$app/state";
    import { toggleParam } from "./browserContext.svelte";

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

    const selectedValues = $derived(page.url.searchParams.getAll(variable));

    // if present, remove, otherwise add
    function toggle(value: string) {
        toggleParam(variable, value);
    }
</script>

<input type="text" placeholder="Filter..." bind:value={filter} />
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<ul class="m-0 flex list-none flex-wrap p-0">
    {#each values as value}
        {@const isActive = selectedValues.includes(value[name])}
        {@const isHighlight = filter == "" || filteredValues.includes(value)}
        <li
            class="item m-[0.1em] cursor-pointer rounded-[0.2em] border border-black/10 px-[0.2em] py-[0.1em] text-[0.9em] text-black/60 opacity-20 hover:bg-gray-100"
            class:bg-[#b6ddf9]={isActive}
            class:opacity-100={isHighlight}
            onclick={() => toggle(value[name])}
        >
            {value[name]}
        </li>
    {/each}
</ul>

<style>
</style>
