<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import NewSegmentation from "./NewSegmentation.svelte";
    import PanelIcon from "../icons/PanelIcon.svelte";
    import { Hide, Show } from "../icons/icons";
    import CreatorSegmentations from "./CreatorSegmentations.svelte";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import DrawingTools from "./DrawingTools.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");

    interface Props {
        active: boolean;
    }
    let { active }: Props = $props();

    const { image } = viewerContext;
    const { instance } = image;
    const { creator } = globalContext;

    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );

    // This is used to not render when the panel is collapsed 
    // Perhaps there is a cleaner solution?
    $effect(() => {
        segmentationOverlay.active = active;
    });

    const segmentationContext = segmentationOverlay.segmentationContext;

    const creators = segmentationOverlay.segmentations.collectSet(
        (a) => a.creator,
    );

    // hide all on load
    const segmentations = instance.segmentations.filter(
        globalContext.segmentationsFilter,
    );
    for (const annotation of $segmentations) {
        segmentationContext.hideCreators.add(annotation.creator);
    }
    // show own segmentations
    segmentationContext.hideCreators.delete(creator);

    function toggleAll(toggle: boolean) {
        if (toggle) {
            segmentationContext.hideSegmentations.clear();
        } else {
            for (const a of segmentationOverlay.segmentations.$) {
                segmentationContext.hideSegmentations.add(a);
            }
        }
    }
</script>

<div class="main">
    <div>
        <DrawingTools />
        <div class="opacity">
            <label>
                Opacity:
                <input
                    type="range"
                    bind:value={segmentationOverlay.alpha}
                    min="0"
                    max="1"
                    step="0.01"
                />
            </label>
        </div>

        <PanelIcon onclick={() => toggleAll(false)} isText={true}>
            <Hide size="1.5em" /> Hide all
        </PanelIcon>
        <PanelIcon onclick={() => toggleAll(true)} isText={true}>
            <Show size="1.5em" /> Show all
        </PanelIcon>

        <ul class="users">
            <!-- show own segmentations first -->
            {#if $creators.has(creator)}
                <li>
                    <CreatorSegmentations {creator} />
                </li>
            {/if}
            {#each $creators as creator_}
                {#if creator_ != creator}
                    <li>
                        <CreatorSegmentations creator={creator_} />
                    </li>
                {/if}
            {/each}
        </ul>
        <NewSegmentation />
    </div>
</div>

<style>
    ul {
        list-style-type: none;
        padding-inline-start: 0em;
        margin: 0;
    }
    div.opacity {
        padding: 0.5em;
        display: flex;
        
        
    }
    label {
        display: flex;
    }
</style>
