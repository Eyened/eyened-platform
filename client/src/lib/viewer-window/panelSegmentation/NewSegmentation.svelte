<script lang="ts">
    import { getContext } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { Writable } from "svelte/store";
    import FeatureSelect from "./FeatureSelect.svelte";
    import { data } from "$lib/datamodel/model";
    import type { Feature } from "$lib/datamodel/feature.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";

    import {
        Segmentation,
        type DataRepresentation,
        type Datatype,
    } from "$lib/datamodel/segmentation.svelte";
    import NewMultiFeature from "./NewMultiFeature.svelte";
    import type { TaskContext } from "$lib/types";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const taskContext = getContext<TaskContext>("taskContext");

    const featureSubsets: { [name: string]: [number] } =
        taskContext?.task?.definition?.config?.featureSubsets || {};

    const { image, axis } = viewerContext;
    const { creator } = globalContext;
    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const segmentationContext = segmentationOverlay.segmentationContext;
    const { features } = data;

    const types = ["Q", "B", "P"];
    let selectedType = $state("Q");

    const dataRepresentations: { [key: string]: DataRepresentation } = {
        Q: "DualBitMask",
        B: "Binary",
        P: "Probability",
    };

    async function create(feature: Feature) {
        globalContext.dialogue = `Creating annotation...`;

        let dataType: Datatype = "R8UI";
        if (selectedType == "P") {
            // TODO: this could perhaps also be R32F?
            dataType = "R8";
        }

        await Segmentation.createFrom(
            image,
            feature,
            creator,
            dataRepresentations[selectedType],
            dataType,
            0.5,
            axis,
            taskContext?.subTask
        );
        segmentationContext.hideCreators.delete(creator);
        globalContext.dialogue = null;
    }

    const availableFeatures = features.filter((f) => true);
    let selectedFeatureId: number | undefined = $state(undefined);
</script>

<div class="new">
    {#if Object.keys(featureSubsets).length > 0}
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
    {/if}

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
        values={availableFeatures}
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
