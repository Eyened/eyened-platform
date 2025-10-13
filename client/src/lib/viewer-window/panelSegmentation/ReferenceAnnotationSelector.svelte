<script lang="ts">
    import { segmentations } from "$lib/data/stores.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext } from "svelte";
    import type { SegmentationGET } from "../../../types/openapi_types";
    import { type Segmentation } from "./segmentationContext.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        image: AbstractImage;
        segmentation: Segmentation;
        resolve: (segmentation: SegmentationGET) => void;
        close: () => void;
    }

    let { image, segmentation, resolve, close }: Props = $props();

    const referenceAnnotations = $derived(
        segmentations.filter(s => s.image_instance_id === image.instance.id)
            .filter(globalContext.segmentationsFilter)
            .filter(
                (a) =>
                    a.data_representation == "Binary" ||
                    a.data_representation == "DualBitMask",
            )
    );
    
    function _resolve(segmentation: SegmentationGET) {
        resolve(segmentation);
        close();
    }
</script>

<div>
    <div>Select reference annotation:</div>
    {#if referenceAnnotations.length == 0}
        <div>No reference annotations found</div>
    {:else}
        <ul>
            {#each referenceAnnotations as reference}
                {@const current = reference.id == segmentation.reference_segmentation_id}
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
