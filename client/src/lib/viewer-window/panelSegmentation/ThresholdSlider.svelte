<script lang="ts">
    import { updateSegmentation } from "$lib/data/api";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext } from "svelte";
    import type { Segmentation } from "./segmentationContext.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        segmentation: Segmentation;
    }
    let { segmentation }: Props = $props();

    let threshold = $state(segmentation.threshold ?? 0.5);
    const canEdit = globalContext.canEdit(segmentation);

    async function onUpdateThreshold() {
        if (canEdit && segmentation.annotation_type === 'grader_segmentation') {
            await updateSegmentation(segmentation.id, { threshold });
        }
    }
</script>

<label>
    <span>Threshold: {threshold}</span>
    <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        bind:value={threshold}        
        onchange={onUpdateThreshold}
    />
</label>

<style>
    label {
        display: flex;
        flex-direction: column;
    }
</style>
