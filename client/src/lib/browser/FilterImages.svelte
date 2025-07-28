<script lang="ts">
    import { data } from "$lib/datamodel/model";
    import ConditionsMultiSelect from "./ConditionsMultiSelect.svelte";
    import DateRangePicker from "./DateRangePicker.svelte";
    import FilterBlock from "./FilterBlock.svelte";

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
            variable: "Segmentation.CreatorName",
            name: "name",
            values: data["creators"].values(),
            title: "Creator (segmentations)",
        },
        {
            variable: "Form.CreatorName",
            name: "name",
            values: data["creators"].values(),
            title: "Creator (forms)",
        },
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

<div class="content">
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

<style>

</style>
