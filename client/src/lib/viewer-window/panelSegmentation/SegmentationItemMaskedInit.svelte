<script lang="ts">
    import type { Annotation } from "$lib/datamodel/annotation.svelte";
    import SegmentationItemMasked from "./SegmentationItemMasked.svelte";

    interface Props {
        annotation: Annotation;
    }

    let { annotation }: Props = $props();
    const { annotationData } = annotation;
</script>

{#each $annotationData as ad (ad.id)}
    {#await ad.value.load()}
        <p>Loading...{annotation.id} [{ad.scanNr}]</p>
    {:then value}
        {#if value?.maskID}
            <SegmentationItemMasked annotationData={ad} maskID={value.maskID} />
        {/if}
    {/await}
{/each}
