<script lang="ts">
    import { data } from "$lib/datamodel/model";
    import ConditionsMultiSelect from "./ConditionsMultiSelect.svelte";
    import DateRangePicker from "./DateRangePicker.svelte";
    import FilterBlock from "./FilterBlock.svelte";
    import { getContext } from "svelte";
    import { BrowserContext } from "./browserContext.svelte";

    let show = $state(false);

    const browserContext = getContext<BrowserContext>("browserContext");

    type FilterItem = {
        variable: string;
        name: string;
        values: any[]; //keyof typeof data;
        title: string;
    };
    const modalities = [
        "AdaptiveOptics",
        "ColorFundus",
        "ColorFundusStereo",
        "RedFreeFundus",
        "ExternalEye",
        "LensPhotograph",
        "Ophthalmoscope",
        "Autofluorescence",
        "FluoresceinAngiography",
        "ICGA",
        "InfraredReflectance",
        "BlueReflectance",
        "GreenReflectance",
        "OCT",
        "OCTA",
    ];
    const filterBlocks: FilterItem[] = [
        {
            variable: "FeatureName",
            name: "name",
            values: data["features"].values(),
            title: "Features",
        },
        {
            variable: "CreatorName",
            name: "name",
            values: data["creators"].values(),
            title: "Creators",
        },
        // TODO: Fix. Broken after database update
        {
            variable: "Modality",
            name: "modality",
            values: modalities.map((k) => ({ modality: k })),
            title: "Modality",
        },
        {
            variable: "ProjectName",
            name: "name",
            values: data["projects"].values(),
            title: "Projects",
        },
        {
            variable: "ManufacturerModelName",
            name: "model",
            values: data["devices"].values(),
            title: "Camera",
        },
    ];

    
</script>

<button onclick={() => (show = true)}>Advanced search</button>
{#if show}
    <div class="content">
        <div>
            <button onclick={() => (show = false)}>Close</button>
        </div>
        <div>
            {#each filterBlocks as { variable, name, values, title }}
                <FilterBlock {title}>
                    <ConditionsMultiSelect {variable} {values} {name} />
                </FilterBlock>
            {/each}
        </div>

        <FilterBlock title="Study Date">
            <DateRangePicker />
        </FilterBlock>
    </div>
{/if}

<style>
    .content {
        position: fixed;
        z-index: 1;
        left: 0;
        top: 0;
        bottom: 0;
        right: 0;
        background-color: rgba(255, 255, 255, 0.99);
        backdrop-filter: blur(5px);
        transition: 0.5s;
        padding: 1em;
        overflow: auto;
    }
</style>
