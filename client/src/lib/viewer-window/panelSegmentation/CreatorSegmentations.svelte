<script lang="ts">
    import type { Creator } from "$lib/datamodel/creator.svelte";
    import { getContext } from "svelte";
    import type { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import SegmentationItem from "./SegmentationItem.svelte";

    interface Props {
        creator: Creator;
    }
    let { creator }: Props = $props();

    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const hideCreators = segmentationOverlay.segmentationContext.hideCreators;
    function toggle() {
        if (hideCreators.has(creator)) {
            hideCreators.delete(creator);
        } else {
            hideCreators.add(creator);
        }
    }
    let segmentations = segmentationOverlay.allSegmentations
        .filter((a) => a.creator.id == creator.id)
        .sort((a, b) => a.id - b.id);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<span class="creator-name" onclick={toggle}>
    {hideCreators.has(creator) ? "►" : "▼"}
    {creator.name}
</span>

{#each $segmentations as segmentation (segmentation.id)}
    <div class="item" class:hide={hideCreators.has(segmentation.creator)}>
        <SegmentationItem {segmentation} />
    </div>
{/each}

<style>
    span.creator-name {
        cursor: pointer;
        background-color: rgba(255, 255, 255, 0.1);
    }
    .creator-name {
        display: flex;
    }
    .creator-name:hover {
        cursor: pointer;
        background-color: rgba(255, 255, 255, 0.4);
    }
    div.item.hide {
        height: 0;
        overflow: hidden;
    }
</style>
