<script lang="ts">
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext } from "svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
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
    const segmentationAnnotations = image.instance.segmentations
        .concat(image.instance.modelSegmentations)
        .filter(globalContext.segmentationsFilter);

    const referenceSegmentations = segmentationAnnotations
        .filter((s) => s != segmentation)
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
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Created By</th>
                <th>Feature</th>
            </tr>
        </thead>
        <tbody>
            {#each $referenceSegmentations as segmentation}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                <tr onclick={() => _resolve(segmentation)}>
                    <td class="annotation-id">[{segmentation.id}]</td>
                    <td>{segmentation.createdBy.name}</td>
                    <td>{segmentation.feature.name}</td>
                </tr>
            {/each}
        </tbody>
    </table>
{:else}
    <div>No segmentations found to import from</div>
{/if}
<button onclick={close}>Cancel</button>

<style>
    table {
        width: 100%;
        border-collapse: collapse;
        max-height: 20em;
        overflow: auto;
    }

    th {
        text-align: left;
        padding: 8px;
        border-bottom: 2px solid rgba(0, 0, 0, 0.3);
        font-weight: bold;
        background-color: #f5f5f5;
    }

    td {
        padding: 8px;
        border-bottom: 1px solid rgba(0, 0, 0, 0.2);
    }

    tr {
        cursor: pointer;
        transition: background-color 0.2s ease;
    }

    tr:hover {
        background-color: #e6fdff;
        cursor: pointer;
    }

    .annotation-id {
        font-size: x-small;
        color: gray;
    }
</style>
