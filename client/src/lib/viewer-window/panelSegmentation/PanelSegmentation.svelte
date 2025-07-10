<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onDestroy, setContext } from "svelte";
    import NewSegmentation from "./NewSegmentation.svelte";
    import PanelIcon from "../icons/PanelIcon.svelte";
    import { Hide, Show } from "../icons/icons";
    import CreatorSegmentations from "./CreatorSegmentations.svelte";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");

    const {
        image: { instance },
    } = viewerContext;

    const { creator } = globalContext;

    const overlay = new SegmentationOverlay(viewerContext, globalContext);
    setContext("segmentationOverlay", overlay);
    // The segmentation overlay is active while this panel is open
    // The overlay is removed when the panel is destroyed
    onDestroy(viewerContext.addOverlay(overlay));

    const { segmentationContext } = overlay;

    const creators = overlay.annotations.collectSet((a) => a.creator);

    // hide all on load
    const segmentations = instance.annotations.filter(
        globalContext.annotationsFilter,
    );
    for (const annotation of $segmentations) {
        segmentationContext.hideCreators.add(annotation.creator);
    }
    // show own segmentations
    segmentationContext.hideCreators.delete(creator);

    function toggleAll(toggle: boolean) {
        if (toggle) {
            segmentationContext.hideAnnotations.clear();
        } else {
            for (const a of overlay.annotations.$) {
                segmentationContext.hideAnnotations.add(a);
            }
        }
    }
</script>

<div class="main">
    <div>
        <PanelIcon onclick={() => toggleAll(false)} isText={true}>
            <Hide size="1.5em" /> Hide all
        </PanelIcon>
        <PanelIcon onclick={() => toggleAll(true)} isText={true}>
            <Show size="1.5em" /> Show all
        </PanelIcon>
        <div>
            <label>
                Opacity:
                <input
                    type="range"
                    bind:value={overlay.alpha}
                    min="0"
                    max="1"
                    step="0.01"
                />
            </label>
        </div>
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
    div.main {
        padding: 0.5em;
    }
    ul {
        list-style-type: none;
        padding-inline-start: 0em;
        margin: 0;
    }
    label {
        display: flex;
    }
</style>
