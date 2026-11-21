<!--
@component
One segmentation row in Layers: color, the name (selects it) and the type letter; eye and Delete at the right. Under it, this slice's area while Area is on.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import LayerRow from "$lib/layers/LayerRow.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import SliceArea from "$lib/layers/SliceArea.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext } from "svelte";
    import FeatureColorPicker from "./FeatureColorPicker.svelte";
    import {
        getSegmentationKey,
        type Segmentation,
    } from "./segmentationContext.svelte";
    import { representationLetter } from "./segmentationUtils";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const segmentationContext = mainViewerContext.segmentationContext;

    interface Props {
        segmentation: Segmentation;
        /** Show this slice's area under the row. */
        showArea: boolean;
        /** Delete asks first; the section owns the modal, because a delete unmounts the row. */
        ondelete: (segmentation: Segmentation) => void;
    }

    let { segmentation, showArea, ondelete }: Props = $props();

    const feature = segmentation.feature;
    const dataRepresentation = segmentation.data_representation;
    const isMulti =
        dataRepresentation == "MultiLabel" ||
        dataRepresentation == "MultiClass";

    const visible = $derived(
        segmentationContext.shownSegmentations.has(
            getSegmentationKey(segmentation),
        ),
    );

    // Must not run inside $derived: getOrCreateSegmentationItem mutates the image cache.
    const segmentationItem =
        segmentationContext.getSegmentationItem(segmentation);
    const isEditable = globalContext.canEdit(segmentation);
    const isEmptyForCurrentSlice = $derived(
        segmentationItem.isEmptyForSlice(viewerContext.index),
    );

    function showOnly(e: MouseEvent) {
        e.preventDefault();
        segmentationContext.showOnlySegmentation(segmentation);
    }

    function toggleActive() {
        segmentationContext.toggleActive(segmentationItem);
        if (
            mainViewerContext.highlightedSegmentationItem === segmentationItem
        ) {
            mainViewerContext.highlightedSegmentationItem = undefined;
        }
    }

    const isActive = $derived(
        segmentationContext.isActiveSegmentation(segmentation),
    );

    function pointerEnter() {
        mainViewerContext.highlightedSegmentationItem = segmentationItem;
    }

    function pointerLeave() {
        mainViewerContext.highlightedSegmentationItem = undefined;
    }
</script>

<LayerRow
    label="{feature.name} segmentation [{segmentation.id}]"
    name={feature.name}
    selected={isActive}
    {visible}
    onselect={toggleActive}
    class={segmentationItem.loading
        ? "opacity-50"
        : !isEditable && isEmptyForCurrentSlice
          ? "opacity-60"
          : isEditable && isEmptyForCurrentSlice && !isActive
            ? "bg-layer-hover-01"
            : ""}
    onpointerenter={pointerEnter}
    onpointerleave={pointerLeave}
>
    {#snippet swatch()}
        {#if !isMulti}<FeatureColorPicker {segmentation} />{/if}
    {/snippet}
    {#snippet tags()}
        <Tag>{representationLetter(dataRepresentation)}</Tag>
    {/snippet}
    {#snippet icons()}
        <IconButton
            size="icon-xs"
            label={visible ? "Hide" : "Show"}
            data-sticky={!visible}
            onclick={() =>
                segmentationContext.toggleShowSegmentation(segmentation)}
            oncontextmenu={showOnly}
        >
            {#if visible}<View />{:else}<ViewOff />{/if}
        </IconButton>
        {#if isEditable}
            <IconButton
                size="icon-xs"
                label="Delete"
                onclick={() => ondelete(segmentation)}
            >
                <TrashCan />
            </IconButton>
        {/if}
    {/snippet}
    <div class="details">
        {#if showArea && !isMulti}
            <SliceArea {segmentation} {segmentationItem} />
        {/if}
        {#if segmentationItem.loading}
            <p class="text-helper-text-01 text-text-secondary">
                Loading segmentation…
            </p>
        {/if}
    </div>
</LayerRow>

<style>
    .details {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0.25rem;
        /* Starts under the colour or name, as the row line's ps-7 does. */
        padding-inline: 1.75rem 0.5rem;
    }
    .details:empty {
        display: none;
    }
</style>
