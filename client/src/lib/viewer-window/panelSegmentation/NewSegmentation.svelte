<script lang="ts">
    import { getContext } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { Readable, Writable } from "svelte/store";
    import FeatureSelect from "./FeatureSelect.svelte";
    import { data } from "$lib/datamodel/model";
    import type { Feature } from "$lib/datamodel/feature.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import { getCompositeFeatures } from "$lib/datamodel/compositeFeature.svelte";
    import { Segmentation, type DataRepresentation, type Datatype } from "$lib/datamodel/segmentation.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { image, axis } = viewerContext;
    const { creator } = globalContext;
    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const segmentationContext = segmentationOverlay.segmentationContext;
    const { features } = data;

    const compositeFeatures = getCompositeFeatures();

    const dialogue = getContext<Writable<any>>("dialogue");

    let selectedFeature: Feature | undefined = $state(undefined);

    const dataRepresentations: { [key: string]: DataRepresentation } = {
        "Q": "DualBitMask",
        "B": "Binary",
        "P": "Probability",
        "MultiLabel": "MultiLabel",
        "MultiClass": "MultiClass",
    }
    
    async function create(
        feature: Feature,
        annotationType: "Q" | "B" | "P" | "MultiLabel" | "MultiClass",
    ) {
        dialogue.set(`Creating annotation...`);

        let dataType: Datatype = "R8UI";
        if (annotationType == "P") {
            dataType = "R8";
        }

        await Segmentation.createFrom(image, feature, creator, dataRepresentations[annotationType], dataType, 0.5, axis);
        segmentationContext.hideCreators.delete(creator);
        dialogue.set(undefined);
    }

    // let selectList: { [name: string]: Feature[] } = $state({});
    // function selectFeatures(featureSet: { [name: string]: string[] }) {
    //     for (const [groupname, featurenames] of Object.entries(featureSet)) {
    //         selectList[groupname] = [];
    //         for (const name of featurenames) {
    //             const feature = features.find((f) => f.name == name);
    //             if (feature) {
    //                 selectList[groupname].push(feature);
    //             }
    //         }
    //     }
    // }
    // if (image.is3D) {
    //     selectFeatures(featureSetOCT);
    // } else {
    //     selectFeatures(featureSetColorFundus);
    // }
    const availableFeatures = features.filter((f) => {
        // TODO: filter features that are not available for the current image?
        return true;
    });

    let selectList = false;
</script>

<div class="new">
    <!-- {#if selectList}
        <div>
            <select bind:value={selectedFeature}>
                <option value="" selected disabled hidden
                    >Select feature:</option
                >
                {#each Object.entries(selectList) as [groupname, features]}
                    <optgroup label={groupname}>
                        {#each features as feature}
                            <option value={feature}>{feature.name}</option>
                        {/each}
                    </optgroup>
                {/each}
            </select>
            <button
                onclick={() => create(selectedFeature!, qType)}
                disabled={selectedFeature == undefined}
            >
                Create
            </button>
        </div>
    {/if} -->
    <FeatureSelect
        name="Feature"
        values={availableFeatures}
        types={["Q", "B", "P"]}
        onselect={(feature, type) => create(feature, type as "Q" | "B" | "P")}
    />

    {#snippet multi(dataRepresentation: "MultiLabel" | "MultiClass")}
        <div>
            <h3>{dataRepresentation}</h3>
            <ul>
                {#each $compositeFeatures.entries() as [parentFeatureId, items]}
                    {@const parentFeature = features.get(parentFeatureId)!}
                    <li>
                        <button
                            onclick={() =>
                                create(parentFeature, dataRepresentation)}
                        >
                            Create new [{parentFeature.name}]
                        </button>
                    </li>
                {/each}
            </ul>
        </div>
    {/snippet}
    {@render multi("MultiLabel")}
    {@render multi("MultiClass")}
</div>

<style>
    div {
        display: flex;
    }
    div.new {
        flex-direction: column;
    }
    select {
        width: 10em;
    }
    ul {
        list-style-type: none;
        padding-inline-start: 0em;
        margin: 0;
    }
</style>
