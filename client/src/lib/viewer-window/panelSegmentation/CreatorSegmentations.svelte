<script lang="ts">
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { getContext } from "svelte";
    import type { CreatorMeta } from "../../../types/openapi_types";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import SegmentationItem from "./SegmentationItem.svelte";

    interface Props {
        creator: CreatorMeta;
    }
    let { creator }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>("viewerWindowContext");
    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );
    const segmentationContext = mainViewerContext.segmentationContext;

    const segmentations = $derived(segmentationContext.segmentations.filter((a) => a.creator.id == creator.id).sort((a, b) => a.id - b.id));
    const hidden = $derived(segmentationContext.creatorHidden.get(creator.id) ?? false);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<span class="creator-name" onclick={() => segmentationContext.toggleShowCreator(creator.id)}>
    {hidden ? "►" : "▼"}
    {creator.name}
</span>



{#each segmentations as segmentation (segmentation.id)}
    <div class="item" class:hide={hidden}>
        <SegmentationItem segmentation={viewerWindowContext.Segmentations.object(segmentation.id)} />
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
