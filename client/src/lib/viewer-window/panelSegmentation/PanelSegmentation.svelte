<script lang="ts">
    import { getContext } from "svelte";
    import NewSegmentation from "./NewSegmentation.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import CreatorSegmentations from "./CreatorSegmentations.svelte";
    import DrawingTools from "./DrawingTools.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        active: boolean;
    }
    let { active }: Props = $props();

    const { creator } = globalContext;

    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );

    // This is used to not render when the panel is collapsed
    // Perhaps there is a cleaner solution?
    $effect(() => {
        segmentationOverlay.active = active;
    });

    const { segmentationContext, allSegmentations } = segmentationOverlay;

    const creators = segmentationOverlay.allSegmentations.collectSet(
        (s) => s.creator,
    );
    const models = segmentationOverlay.allModelSegmentations.collectSet(
        (s) => s.model,
    );
    // hide all on load
    for (const segmentation of $allSegmentations) {
        segmentationContext.hideCreators.add(segmentation.creator);
    }
    // show own segmentations
    segmentationContext.hideCreators.delete(creator);
</script>

<div class="main">
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

    <ul class="users">
        {#each $models as model}
            <li>
                <CreatorSegmentations {model} />
            </li>
        {/each}
    </ul>

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

<style>
    div {
        display: flex;
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
