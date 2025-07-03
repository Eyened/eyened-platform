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
    const { hideCreators } = segmentationOverlay.segmentationContext;
    function toggle() {
        if (hideCreators.has(creator)) {
            hideCreators.delete(creator);
        } else {
            hideCreators.add(creator);
        }
    }
    let annotations = segmentationOverlay.annotations
        .filter((a) => a.creator == creator)
        .sort((a, b) => a.id - b.id);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<span class="creator-name" onclick={toggle}>
    {hideCreators.has(creator) ? "►" : "▼"}
    {creator.name}
</span>

{#each $annotations as annotation (annotation.id)}
    <div class="item" class:hide={hideCreators.has(annotation.creator)}>
        <SegmentationItem {annotation} />
    </div>
{/each}

<style>
    span.creator-name {
        cursor: pointer;
    }
    .creator-name {
        display: flex;
    }
    .creator-name:hover {
        cursor: pointer;
        background-color: rgba(255, 255, 255, 0.1);
    }
    div.item.hide {
        height: 0;
        overflow: hidden;
    }
</style>
