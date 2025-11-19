<script lang="ts">
    import { updateSegmentation } from "$lib/data/api";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext } from "svelte";
    import type { Segmentation } from "./segmentationContext.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        segmentation: Segmentation;
        segmentationItem: SegmentationItem;
    }
    let { segmentation, segmentationItem }: Props = $props();

    const canEdit = globalContext.canEdit(segmentation);

    let pendingUpdate = Promise.resolve();
    async function onUpdateThreshold() {
        if (canEdit) {
            await pendingUpdate;
            pendingUpdate = updateSegmentation(segmentation.id, { threshold: segmentationItem.threshold });
        }
    }

</script>

<label>
    <span>Threshold: {segmentationItem.threshold.toFixed(2)}</span>
    <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        bind:value={segmentationItem.threshold}
        onchange={onUpdateThreshold}
    />
</label>

<style>
    label {
        display: flex;
        flex-direction: column;
    }
</style>
