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
    // for (const ad of segmentation.annotationData.$) {
    //     threshold = ad.valueFloat || 0.5;
    // }
    const canEdit = globalContext.canEdit(segmentation);

    $effect(() => {
        // for (const ad of annotation.annotationData.$) {
        //     ad.valueFloat = threshold;
        // }
    });

    function onUpdateThreshold() {
        // for (const ad of annotation.annotationData.$) {
        //     ad.valueFloat = threshold;
        //     if (canEdit) {
        //         // updates the threshold value in the annotation data on server
        //         ad.update({ valueFloat: threshold });
        //     }
        // }
        segmentation.update({ threshold: threshold });
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
