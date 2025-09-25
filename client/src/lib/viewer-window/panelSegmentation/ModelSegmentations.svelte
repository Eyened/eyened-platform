<script lang="ts">
    import type { MainViewerContext } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import { getContext } from "svelte";
    import type { ModelMeta } from "../../../types/openapi_types";
    import SegmentationItem from "./SegmentationItem.svelte";

    interface Props {
        model: ModelMeta;
    }
    let { model }: Props = $props();

    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );

    const allModelSegmentations = mainViewerContext.allModelSegmentations;

    let segmentations = allModelSegmentations
        .filter((a) => a.creator.id == model.id)
        .sort((a, b) => a.id - b.id);
</script>

{#each segmentations as segmentation (segmentation.id)}
    <SegmentationItem {segmentation} style="AI" />
{/each}
