<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getCompositeFeatures } from "$lib/datamodel/compositeFeature.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onMount } from "svelte";
    import * as Select from "../../components/ui/select";
    import { ViewerWindowContext } from "../viewerWindowContext.svelte";

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

    onMount(async () => {
        await globalContext.ensureFeaturesLoaded();
    });

    // Use repo to drive the UI list of parents-with-subfeatures
    const featuresWithSubfeatures = $derived(
        globalContext.features.all.filter(f => (f.subfeatures ?? []).length > 0)
    );


    let selectedFeatureId: number | undefined = $state(undefined);
    async function create() {
        if (selectedFeatureId == undefined) {
            return;
        }
        globalContext.dialogue = `Creating annotation...`;

        let dataType: Datatype = "R8UI";

        await viewerWindowContext.Segmentations.createFrom(
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

<!-- <Select.Root type="single">
  <Select.Trigger class="w-[180px]"></Select.Trigger>
  <Select.Content>
    <Select.Item value="light">Light</Select.Item>
    <Select.Item value="dark">Dark</Select.Item>
    <Select.Item value="system">System</Select.Item>
  </Select.Content>
</Select.Root> -->

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
        <!-- <select bind:value={selectedFeatureId}>
            {#each featuresWithSubfeatures as f}
                <option value={f.id}>
                    {f.name}
                </option>
            {/each}
        </select> -->
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
