<script lang="ts">
    import type { FilterList } from "$lib/datamodel/itemList";

    interface Named {
        name: string;
    }

    interface Props<T extends Named> {
        name: string;
        values: FilterList<T>;
        types: string[];
        onselect: (value: T, type: string) => void;
    }
    let { name, values, types, onselect }: Props<any> = $props();
    export const placeholder = "Search...";
    let filter = $state("");
    let filtered = $derived.by(() => {
        const lowerFilter = filter.toLowerCase();
        return values.filter((value) => {
            if (filter) {
                return value.name.toLowerCase().includes(lowerFilter);
            } else {
                return false;
            }
        });
    });
    let selectedType = $state("Q");
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div>
    <div>
        <label>
            {name}:
            <input type="text" {placeholder} bind:value={filter} />
        </label>
    </div>
    <div>   
        {#each types as type}
            <label>
                <input type="radio" name="type" value={type} bind:group={selectedType} />
                {type}
            </label>
        {/each}
    </div>
    <ul>
        {#each $filtered as feature}
            <li class="item" onclick={() => onselect(feature, selectedType)}>
                {feature.name}
            </li>
        {/each}
    </ul>
</div>

<style>
    ul {
        padding: 0;
        margin: 0;
        list-style-type: none;
        flex: 0;
    }
    li.item {
        font-size: 0.9em;
        color: rgba(255, 255, 255, 0.5);
        cursor: pointer;
        padding: 0.1em 0.2em;
        margin: 0.1em;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 0.2em;
    }
    li:hover {
        background-color: rgba(255, 255, 255, 0.3);
        cursor: pointer;
    }
</style>
