<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import FeatureSelect from "./FeatureSelect.svelte";

    import {
        type DataRepresentation,
        type Datatype
    } from "$lib/datamodel/segmentation.svelte";
    import type { TaskContext } from '$lib/tasks/TaskContext.svelte';
    import type { FeatureGET } from "../../../types/openapi_types";
    import { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import NewMultiFeature from "./NewMultiFeature.svelte";
    import type { Segmentation } from "./segmentationContext.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const viewerWindowContext = getContext<ViewerWindowContext>("viewerWindowContext");
    const taskContext = getContext<TaskContext>("taskContext");



    // const featureSubsets: { [name: string]: [number] } =
    //     taskContext?.task?.definition?.config?.featureSubsets || {};

    const { image, axis } = viewerContext;
    const { user: creator } = globalContext;
    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );
    const segmentationContext = mainViewerContext.segmentationContext;

    const types = ["Q", "B", "P"];
    let selectedType = $state("Q");

    const dataRepresentations: { [key: string]: DataRepresentation } = {
        Q: "DualBitMask",
        B: "Binary",
        P: "Probability",
    };

    async function create(feature: FeatureGET) {
        globalContext.dialogue = `Creating annotation...`;

        let dataType: Datatype = "R8UI";
        if (selectedType == "P") {
            // TODO: this could perhaps also be R32F?
            dataType = "R8";
        }

        const segmentation = await viewerWindowContext.Segmentations.createFrom(
            image,
            feature.id,
            dataRepresentations[selectedType],
            dataType,
            0.5,
            axis,
            taskContext?.subTask?.id
        ) as Segmentation

        // TODO: find a cleaner way to do this
        segmentation.gid = `${segmentation.annotation_type}-${segmentation.id}` 
        const segmentationItem = image.getSegmentationItem(segmentation);

        segmentationContext.segmentationItem = segmentationItem

        globalContext.dialogue = null;
    }

    const availableFeatures = globalContext.features.all.filter((f) => true);
    let selectedFeatureId: number | undefined = $state(undefined);
    
</script>

<div class="new">
    <!-- {#if Object.keys(featureSubsets).length > 0}
        <div>
            <select bind:value={selectedFeatureId}>
                <option value="" selected disabled hidden>
                    Select feature:
                </option>
                {#each Object.entries(featureSubsets) as [groupname, featureId]}
                    <optgroup label={groupname}>
                        {#each featureId as featureId}
                            {@const feature = features.get(featureId)}
                            {#if feature}
                                <option value={featureId}>
                                    {feature.name}
                                </option>
                            {:else}
                                <option value={featureId} disabled>
                                    {featureId} (not available)
                                </option>
                            {/if}
                        {/each}
                    </optgroup>
                {/each}
            </select>
            <button
                onclick={() => create(features.get(selectedFeatureId!)!)}
                disabled={selectedFeatureId == undefined}
            >
                Create
            </button>
        </div>
    {/if} -->

    <div>
        <span>Type:</span>
        {#each types as type}
            <label>
                <input
                    type="radio"
                    name="type"
                    value={type}
                    bind:group={selectedType}
                />
                {type}
            </label>
        {/each}
    </div>
    <FeatureSelect
        values={globalContext.features.all}
        onselect={(feature) => create(feature)}
    />
    <NewMultiFeature dataRepresentation="MultiLabel" />
    <NewMultiFeature dataRepresentation="MultiClass" />
</div>

<style>
    div {
        display: flex;
    }
    div.new {
        flex-direction: column;
    }
</style>
