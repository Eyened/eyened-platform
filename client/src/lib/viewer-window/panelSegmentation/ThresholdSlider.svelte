<script lang="ts">
    import { SliderField } from "$lib/components/ui/slider/index.js";
    import { updateSegmentation } from "$lib/data/api";
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

    // Saves in order, so the last value set is the one stored.
    let pendingUpdate = Promise.resolve();
    async function save() {
        if (!canEdit) return;
        await pendingUpdate;
        pendingUpdate = updateSegmentation(segmentation.id, {
            threshold: segmentationItem.threshold,
        });
    }
</script>

<SliderField
    labelText="Threshold"
    value={segmentationItem.threshold ?? segmentation.threshold ?? 0.5}
    onchange={(v) => (segmentationItem.threshold = v)}
    oncommit={save}
    min={0}
    max={1}
    step={0.01}
    decimals={2}
/>
