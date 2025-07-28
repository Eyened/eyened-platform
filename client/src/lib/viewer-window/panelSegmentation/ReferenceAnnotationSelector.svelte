<script lang="ts">
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext } from "svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        image: AbstractImage;
        segmentation: Segmentation;
        resolve: (segmentation: Segmentation) => void;
        close: () => void;
    }

    let { image, segmentation, resolve, close }: Props = $props();

    const referenceAnnotations = image.instance.segmentations
        .filter(globalContext.segmentationsFilter)
        .filter(
            (a) =>
                a.dataRepresentation == "Binary" ||
                a.dataRepresentation == "DualBitMask",
        );
    function _resolve(segmentation: Segmentation) {
        resolve(segmentation);
        close();
    }
</script>

<div>
    <div>Select reference annotation:</div>
    {#if $referenceAnnotations.length == 0}
        <div>No reference annotations found</div>
    {:else}
        <ul>
            {#each $referenceAnnotations as reference}
                {@const current = reference.id == segmentation.referenceId}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                <li onclick={() => _resolve(reference)} class:current>
                    <span>[{reference.id}]</span>
                    <span>{reference.feature.name}</span>
                    <span>{reference.creator.name}</span>
                </li>
            {/each}
        </ul>
    {/if}
    <button onclick={close}>Cancel</button>
</div>

<style>
    ul {
        list-style-type: none;
        padding: 0;
    }
    li {
        padding: 0.5em;
        border-bottom: 1px solid #ccc;
        cursor: pointer;
    }
    li.current {
        background-color: #f0fff0;
    }
    li:hover {
        background-color: #f0f0f0;
    }
</style>
