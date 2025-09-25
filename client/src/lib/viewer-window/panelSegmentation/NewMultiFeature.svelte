<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getCompositeFeatures } from "$lib/datamodel/compositeFeature.svelte";
    import { data } from "$lib/datamodel/model";
    import { Segmentation, type Datatype } from "$lib/datamodel/segmentation.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onMount } from "svelte";

    export interface Props {
        dataRepresentation: "MultiLabel" | "MultiClass";
    }

    const { dataRepresentation }: Props = $props();
    const viewerContext = getContext<ViewerContext>("viewerContext");
        const { image, axis } = viewerContext;
    const globalContext = getContext<GlobalContext>("globalContext");
    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );
    const segmentationContext = mainViewerContext.segmentationContext;
    const { user: creator } = globalContext;
    const compositeFeatures = getCompositeFeatures();
    const features = data.features;

    onMount(async () => {
        await globalContext.ensureFeaturesLoaded();
    });

    // Use repo to drive the UI list of parents-with-subfeatures
    const featuresWithSubfeatures = $derived(
        globalContext.features.all.filter(f => (f.subfeatures ?? []).length > 0)
    );

    $effect(() => {
        console.log(globalContext.features.all);
    });

    $effect(() => {
        console.log(featuresWithSubfeatures);
    });

    let selectedFeatureId: number | undefined = $state(undefined);
    async function create() {
        if (selectedFeatureId == undefined) {
            return;
        }
        globalContext.dialogue = `Creating annotation...`;

        let dataType: Datatype = "R8UI";
        const feature = features.get(selectedFeatureId)!; // datamodel Feature instance

        await Segmentation.createFrom(
            image,
            feature,
            creator,
            dataRepresentation,
            dataType,
            0.5,
            axis,
        );
        segmentationContext.hiddenCreators.delete(creator);
        globalContext.dialogue = null;
    }
    
</script>

<div class="multi">
    <div class="header">{dataRepresentation}</div>
    <form onsubmit={create}>
        <select bind:value={selectedFeatureId}>
            {#each featuresWithSubfeatures as f}
                <option value={f.id}>
                    {f.name} ({(f.subfeatures ?? []).join(', ')})
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
