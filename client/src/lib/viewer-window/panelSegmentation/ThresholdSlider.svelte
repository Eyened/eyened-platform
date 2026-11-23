<script lang="ts">
    import { SliderField } from "$lib/components/ui/slider/index.js";
    import { thresholdSaver } from "$lib/saving/thresholdSavers";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import { getContext } from "svelte";
    import type { Segmentation } from "./segmentationContext.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    let {
        segmentation,
        segmentationItem,
    }: { segmentation: Segmentation; segmentationItem: SegmentationItem } =
        $props();

    const canEdit = globalContext.canEdit(segmentation);

    // One request at a time; the newest value is the one stored.
    function save() {
        if (!canEdit) return;
        thresholdSaver(segmentation, segmentationItem.image.image_id).edit(
            segmentationItem.threshold,
        );
    }
</script>

<SliderField
    labelText="Threshold"
    value={segmentationItem.threshold}
    onchange={(v) => (segmentationItem.threshold = v)}
    oncommit={save}
    min={0}
    max={1}
    step={0.01}
    decimals={2}
/>
