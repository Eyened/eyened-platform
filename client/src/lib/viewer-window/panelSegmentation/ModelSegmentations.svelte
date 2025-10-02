<script lang="ts">
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { getContext } from "svelte";
    import type { ModelMeta } from "../../../types/openapi_types";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import SegmentationItem from "./SegmentationItem.svelte";

    interface Props {
        model: ModelMeta;
    }
    let { model }: Props = $props();
    const viewerWindowContext = getContext<ViewerWindowContext>("viewerWindowContext");
    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );
    const segmentationContext = mainViewerContext.segmentationContext;

    let segmentations = segmentationContext.segmentations
        .filter((a) => a.annotation_type == "model_segmentation")
        .filter((a) => a.creator.id == model.id)
        .sort((a, b) => a.id - b.id);
</script>

{#each segmentations as segmentation (segmentation.id)}
    <SegmentationItem segmentation={segmentation} style="AI" />
{/each}
