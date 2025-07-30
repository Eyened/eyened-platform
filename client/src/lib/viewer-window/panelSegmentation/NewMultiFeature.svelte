<script lang="ts">
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { getCompositeFeatures } from "$lib/datamodel/compositeFeature.svelte";
    import { data } from "$lib/datamodel/model";
    import { Segmentation, type Datatype } from "$lib/datamodel/segmentation.svelte";
    import type { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";

    export interface Props {
        dataRepresentation: "MultiLabel" | "MultiClass";
    }

    const { dataRepresentation }: Props = $props();
    const viewerContext = getContext<ViewerContext>("viewerContext");
        const { image, axis } = viewerContext;
    const globalContext = getContext<GlobalContext>("globalContext");
    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const segmentationContext = segmentationOverlay.segmentationContext;
    const { creator } = globalContext;
    const compositeFeatures = getCompositeFeatures();
    const features = data.features;


    let selectedFeatureId: number | undefined = $state(undefined);
    async function create() {
        if (selectedFeatureId == undefined) {
            return;
        }
        globalContext.dialogue = `Creating annotation...`;

        let dataType: Datatype = "R8UI";
        const feature = features.get(selectedFeatureId)!;

        await Segmentation.createFrom(
            image,
            feature,
            creator,
            dataRepresentation,
            dataType,
            0.5,
            axis,
        );
        segmentationContext.hideCreators.delete(creator);
        globalContext.dialogue = null;
    }
    
</script>

<div class="multi">
    <div class="header">{dataRepresentation}</div>
    <form onsubmit={create}>
        <select bind:value={selectedFeatureId}>
            {#each $compositeFeatures.keys() as parentFeatureId}
                <option value={parentFeatureId}>
                    {features.get(parentFeatureId)!.name}
                </option>
            {/each}
        </select>
        <button type="submit" disabled={selectedFeatureId == undefined}>
            Create
        </button>
    </form>
</div>

<style>
    div {
        display: flex;
    }
    div.header {
        font-weight: bold;
    }
    div.multi {
        flex-direction: column;
    }
    select {
        width: 10em;
    }
    
    div.multi {
        flex-direction: column;
    }
</style>
