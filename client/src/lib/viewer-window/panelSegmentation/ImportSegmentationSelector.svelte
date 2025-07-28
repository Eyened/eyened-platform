<script lang="ts">
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext } from "svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { constructors } from "$lib/webgl/segmentationState";
    import { converters } from "$lib/webgl/segmentationConverter";
    import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        image: AbstractImage;
        segmentation: Segmentation;
        close: () => void;
        resolve: (segmentation: Segmentation) => void;
    }

    let { image, segmentation, resolve, close }: Props = $props();
    const segmentationAnnotations = image.instance.segmentations.filter(
        globalContext.segmentationsFilter,
    );

    const referenceSegmentations = segmentationAnnotations
        .filter((s) => s.id != segmentation.id)
        .filter((other) => {
            const from = segmentation.dataRepresentation;
            const to = other.dataRepresentation;

            const key = `${from}->${to}`;
            // filter out conversions that are not supported
            return from == to || key in converters;
        });

    function _resolve(segmentation: Segmentation) {
        resolve(segmentation);
        close();
    }
</script>

{#if $referenceSegmentations.length > 0}
    <div>Select segmentation to import from:</div>
    <ul>
        {#each $referenceSegmentations as segmentation}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
            <li onclick={() => _resolve(segmentation)}>
                <div class="annotation-id">
                    [{segmentation.id}]
                </div>
                <div>{segmentation.creator.name}</div>
                <div>{segmentation.feature.name}</div>
            </li>
        {/each}
    </ul>
{:else}
    <div>No segmentations found to import from</div>
{/if}
<button onclick={close}>Cancel</button>

<style>
    ul {
        display: grid;
        grid-template-columns: 0fr 1fr 1fr;

        list-style-type: none;
        padding: 0;
        max-height: 20em;
        overflow: auto;
    }

    li {
        display: contents;
        cursor: pointer;
    }

    div.annotation-id {
        font-size: x-small;
        color: gray;
    }
    li > div {
        padding: 0.5em;
        align-items: center;
        display: flex;
        border-bottom: 1px solid rgba(0, 0, 0, 0.2);
    }
    li.hover > div {
        background-color: #e6fdff;
    }
    li.selected > div {
        background-color: #43ff46;
    }
</style>
