<script lang="ts">
    import { getContext } from "svelte";
    import type { StudyObject } from "../data/objects.svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import SeriesComponent from "./SeriesComponent.svelte";

    interface Props {
        study: StudyObject;
        laterality: "L" | "R" | null;
    }

    let { study, laterality }: Props = $props();

    const eye = laterality ? { L: "OS", R: "OD" }[laterality] : "OD/OS?";

    const browserContext = getContext<BrowserContext>("browserContext");
    
    // Get all instances from all series, then filter by instance laterality
    const eyeImages = study.$.series!
        .flatMap((series) => series.instance_ids ?? [])
        .map((id) => browserContext.InstanceRepo.store[id])
        .filter((instance) => instance && instance.laterality == laterality);
    
    // Group images back into series for display
    const eyeSeries = study.$.series!.filter((series) => 
        series.instance_ids?.some((id) => 
            eyeImages.some((img) => img.id === id)
        )
    );
    
    function open() {
        const numbers = eyeImages.map((img) => img.id);
        browserContext.openTab(numbers);
    }
</script>

{#if eyeSeries.length}

    <div class="outer flex flex-1 flex-col p-2">
        <h3 class="m-0 text-base flex items-center gap-4">
            {eye}
            {#if eyeSeries.length > 0}
                <button class="link bg-transparent border border-black/20 rounded-[2px] text-inherit cursor-pointer hover:bg-black/5" onclick={open}>
                    Open all {eye} images</button
                >
            {/if}
        </h3>
        <div class="series-container flex flex-row flex-wrap content-start flex-1">
            {#each [...eyeSeries].sort((a, b) => a.id - b.id) as series (series.id)}
                <SeriesComponent {series} {laterality} />
            {/each}
        </div>
    </div>
{/if}
