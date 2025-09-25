<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { MainViewerContext } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import { getContext } from "svelte";
    import CreatorSegmentations from "./CreatorSegmentations.svelte";
    import DrawingTools from "./DrawingTools.svelte";
    import ModelSegmentations from "./ModelSegmentations.svelte";
    import NewSegmentation from "./NewSegmentation.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        active: boolean;
    }
    let { active }: Props = $props();

    const { user: creator } = globalContext;

    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );

    // This is used to not render when the panel is collapsed
    // Perhaps there is a cleaner solution?
    $effect(() => {
        mainViewerContext.active = active;
    });

    const { segmentationContext, allSegmentations, allModelSegmentations } = mainViewerContext;


    // iterate segmentations and add creators and models
    for (const segmentation of allSegmentations) {
        segmentationContext.creators.set(segmentation.creator.id, segmentation.creator);
    }
    const creatorIds = allSegmentations.map(s => s.creator.id);
    segmentationContext.creatorIds = creatorIds;

    for (const segmentation of allModelSegmentations) {
        console.log(segmentation);
        segmentationContext.models.set(segmentation.creator.id, segmentation.creator);
    }
    const modelIds = allModelSegmentations.map(s => s.creator.id);
    segmentationContext.modelIds = modelIds;

    segmentationContext.creatorIds = segmentationContext.creatorIds.filter(id => id !== creator.id);

</script>

<div class="main">
    <div class="models">
        <ul class="users">
            {#each segmentationContext.orderedModels as model}
                <li>
                    <ModelSegmentations {model} />
                </li>
            {/each}
        </ul>
    </div>
    <DrawingTools />
    <div class="opacity">
        <label>
            Opacity:
            <input
                type="range"
                bind:value={mainViewerContext.alpha}
                min="0"
                max="1"
                step="0.01"
            />
        </label>
    </div>

    <ul class="users">
        {#each segmentationContext.orderedCreators as creator_}
            {#if creator_.id != creator.id}
                <li>
                    <CreatorSegmentations creator={creator_} />
                </li>
            {/if}
        {/each}
    </ul>
    <NewSegmentation />
</div>

<style>
    div {
        display: flex;
    }
    div.models {
        flex: 1;
        flex-direction: column;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        padding-bottom: 0.5em;
    }
    ul {
        list-style-type: none;
        padding-inline-start: 0em;
        margin: 0;
    }
    div.opacity {
        padding: 0.5em;
    }
    div.main {
        flex: 1;
        flex-direction: column;
    }
    label {
        display: flex;
    }
</style>
