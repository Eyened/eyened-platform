<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getCompositeFeatures } from "$lib/datamodel/compositeFeature.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onMount } from "svelte";
    import * as Select from "../../components/ui/select";
    import { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import { createSegmentationFrom, features } from "$lib/data";
	import type { Datatype } from "$lib/datamodel/segmentation.svelte";
    export interface Props {
        dataRepresentation: "MultiLabel" | "MultiClass";
    }

    const { dataRepresentation }: Props = $props();
    const viewerWindowContext = getContext<ViewerWindowContext>("viewerWindowContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
        const { image, axis } = viewerContext;
    const globalContext = getContext<GlobalContext>("globalContext");
    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );
    const segmentationContext = mainViewerContext.segmentationContext;
    const { user: creator } = globalContext;
    const compositeFeatures = getCompositeFeatures();


    // Use repo to drive the UI list of parents-with-subfeatures
    const featuresWithSubfeatures = $derived(
        features.filter(f => (f.subfeatures ?? []).length > 0)
    );


    let selectedFeatureId: number | undefined = $state(undefined);
    async function create() {
        if (selectedFeatureId == undefined) {
            return;
        }
        globalContext.dialogue = `Creating annotation...`;

        let dataType: Datatype = "R8UI";

        await createSegmentationFrom(
            image,
            selectedFeatureId,
            dataRepresentation,
            dataType,
            0.5,
            axis,
        );
        segmentationContext.creatorHidden.set(creator.id, false);

        globalContext.dialogue = null;
    }
    
</script>

<div class="multi">
    <div class="header">{dataRepresentation}</div>
    <form onsubmit={create}>
        <Select.Root type="single" bind:value={selectedFeatureId} size="xs">
            <Select.Trigger class="w-[180px]">
                {selectedFeatureId ? featuresWithSubfeatures.find(f => f.id === selectedFeatureId)?.name : "Select feature"}
            </Select.Trigger>
            <Select.Content>
                {#each featuresWithSubfeatures as f}
                    <Select.Item value={f.id}>
                        {f.name}
                    </Select.Item>
                {/each}
            </Select.Content>
        </Select.Root>
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
