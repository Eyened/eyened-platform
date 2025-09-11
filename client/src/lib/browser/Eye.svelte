<script lang="ts">
    import { getContext } from "svelte"
    import type { components } from "../../types/openapi"
    import type { BrowserContext } from "./browserContext.svelte"
    import SeriesComponent from "./SeriesComponent.svelte"
    type Study = components['schemas']['StudyGET'];
    type Series = components['schemas']['SeriesGET'];

    interface Props {
        study: Study;
        laterality: "L" | "R" | null;
    }

    let { study, laterality }: Props = $props();

    const eye = laterality ? { L: "OS", R: "OD" }[laterality] : "OD/OS?";

    const browserContext = getContext<BrowserContext>("browserContext");

    const eyeSeries = study.series!.filter((series) => series.laterality == laterality);

    function open() {
        const numbers = eyeSeries
            .sort((a, b) => a.id - b.id)
            .flatMap((series) =>
                series.instance_ids
            ) ?? [];
        browserContext.openTab(numbers);
    }
</script>

{#if study.series!.length}
    <div class="outer">
        <h3>
            {eye}
            {#if eyeSeries.length > 0}
                <button class="link" onclick={open}>
                    Open all {eye} images</button
                >
            {/if}
        </h3>
        <div class="series-container">
            {#each [...eyeSeries].sort((a, b) => a.id - b.id) as series (series.id)}
                <SeriesComponent {series} {laterality} />
            {/each}
        </div>
    </div>
{/if}

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
