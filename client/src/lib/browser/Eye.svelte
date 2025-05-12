<script lang="ts">
    import type { Study } from "$lib/datamodel/study";
    import SeriesComponent from "./SeriesComponent.svelte";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";

    interface Props {
        study: Study;
        laterality: "L" | "R";
    }

    let { study, laterality }: Props = $props();

    const eye = { L: "OS", R: "OD" }[laterality];
    const filtered = study.instances.filter(
        (instance) => instance.laterality == laterality,
    );
    const bySeries = filtered.collectSet((instance) => instance.series);
    const browserContext = getContext<BrowserContext>("browserContext");

    function open() {
        const numbers = [...$bySeries]
            .sort((a, b) => a.id - b.id)
            .flatMap((series) =>
                series.instances
                    .map((instance) => instance.id).$
                    .sort(),
            );
        browserContext.openTab(numbers);
    }
</script>

<div class="outer">
    <h3>
        {eye}
        {#if $bySeries.size > 0}
            <button class="link" onclick={open}> Open all {eye} images</button>
        {/if}
    </h3>
    <div class="series-container">
        {#each [...$bySeries].sort((a, b) => a.id - b.id) as series (series.id)}
            <SeriesComponent {series} {laterality} />
        {/each}
    </div>
</div>

<style>
    div {
        display: flex;
    }
    h3 {
        margin: 0;
        font-size: normal;
        display: flex;
        align-items: center;
        gap: 1em;
    }
    button.link {
        background: none;
        border: 1px solid rgba(0, 0, 0, 0.2);
        border-radius: 2px;
        color: inherit;
        font: normal;
        cursor: pointer;
    }
    button.link:hover {
        background: rgba(0, 0, 0, 0.05);
    }
    .outer {
        flex: 1;
        flex-direction: column;
        padding: 0.5em;
    }
    .series-container {
        flex-wrap: wrap;
        align-content: flex-start;
        flex: 1;
        flex-direction: row;
    }
</style>
