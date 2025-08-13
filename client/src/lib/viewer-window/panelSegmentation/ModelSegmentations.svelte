<script lang="ts">
    import type { Model } from "$lib/datamodel/segmentation.svelte";
    import { getContext } from "svelte";
    import type { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import SegmentationItem from "./SegmentationItem.svelte";

    interface Props {
        model: Model;
    }
    let { model }: Props = $props();

    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );

    const allModelSegmentations = segmentationOverlay.allModelSegmentations;

    let segmentations = allModelSegmentations
        .filter((a) => a.model.id == model.id)
        .sort((a, b) => a.id - b.id);
</script>

{#each $segmentations as segmentation (segmentation.id)}
    <SegmentationItem {segmentation} style="AI" />
{/each}
