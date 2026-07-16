<script lang="ts">
    import type { FeatureGET } from "../../../types/openapi_types";

    interface Named {
        name: string;
    }

    interface Props<T extends Named> {
        values: FeatureGET[];
        onselect: (value: T) => void;
        /** Keep search field in sync when feature is chosen elsewhere (e.g. native select). */
        selectedName?: string;
    }
    let { values, onselect, selectedName = "" }: Props<any> = $props();
    const placeholder = "Search feature...";
    let filter = $state("");
    /** After a pick, hide matches until the user edits the search text again. */
    let listHidden = $state(false);

    let filtered = $derived.by(() => {
        if (listHidden || !filter.trim()) {
            return [];
        }
        const lowerFilter = filter.toLowerCase();
        return values.filter((value) =>
            value.name.toLowerCase().includes(lowerFilter),
        );
    });

    function onFilterInput() {
        listHidden = false;
    }

    function pick(feature: FeatureGET) {
        filter = feature.name;
        listHidden = true;
        onselect(feature);
    }

    $effect(() => {
        if (selectedName) {
            filter = selectedName;
            listHidden = true;
        }
    });
</script>

<div class="feature-select">
    <input
        type="text"
        {placeholder}
        bind:value={filter}
        oninput={onFilterInput}
    />

    {#if filtered.length > 0}
        <ul>
            {#each filtered as feature (feature.id)}
                <li>
                    <button
                        type="button"
                        class="item"
                        onclick={() => pick(feature)}
                    >
                        {feature.name}
                    </button>
                </li>
            {/each}
        </ul>
    {/if}
</div>

<style>
    .feature-select {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        width: 100%;
    }
    input[type="text"] {
        width: 100%;
        box-sizing: border-box;
    }
    ul {
        padding: 0;
        margin: 0;
        list-style-type: none;
        max-height: 10rem;
        overflow-y: auto;
    }
    li {
        margin: 0;
    }
    button.item {
        display: block;
        width: 100%;
        text-align: left;
        font-size: 0.9em;
        color: rgba(255, 255, 255, 0.85);
        cursor: pointer;
        padding: 0.25em 0.35em;
        margin: 0;
        border: none;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 0.2em;
        background: transparent;
    }
    button.item:hover {
        background-color: rgba(255, 255, 255, 0.25);
    }
</style>
