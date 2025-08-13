<script lang="ts">
    import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { getContext } from "svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        segmentation: Segmentation;
    }
    let { segmentation }: Props = $props();

    let threshold = $state(0.5);
    threshold = segmentation.threshold;
    const canEdit = globalContext.canEdit(segmentation);


    function onUpdateThreshold() {
        if (canEdit) {
            segmentation.update({ threshold: segmentation.threshold });
        }
    }
</script>

<label>
    <span>Threshold: {segmentation.threshold}</span>
    <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        bind:value={segmentation.threshold}        
        onchange={onUpdateThreshold}
    />
</label>

<style>
    label {
        display: flex;
        flex-direction: column;
    }
</style>
