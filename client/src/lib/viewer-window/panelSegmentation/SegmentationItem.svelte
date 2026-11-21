<!--
@component
One segmentation row in Layers: colour, the name (sets or unsets the current row) and the type letter; Mask with reference, eye (right-click shows only this) and Delete at the right.
Under it: the current row's save state, this slice's area, then the row's details.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { tagSegmentation, untagSegmentation } from "$lib/data/helpers";
    import Tagger from "$lib/tags/Tagger.svelte";
    import LayerRow from "$lib/layers/LayerRow.svelte";
    import type { SegmentationGET } from "../../../types/openapi_types";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import SliceArea from "$lib/layers/SliceArea.svelte";
    import SyncStatus from "$lib/layers/SyncStatus.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import Intersect from "carbon-icons-svelte/lib/Intersect.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import View from "carbon-icons-svelte/lib/View.svelte";
    import ViewOff from "carbon-icons-svelte/lib/ViewOff.svelte";
    import { getContext } from "svelte";
    import CCPanel from "./CCPanel.svelte";
    import { duplicate } from "./duplicate_utils";
    import DuplicateAnnotationPanel from "./DuplicateAnnotationPanel.svelte";
    import FeatureColorPicker from "./FeatureColorPicker.svelte";
    import ImportPanel from "./ImportPanel.svelte";
    import MultiFeatureSelector from "./MultiFeatureSelector.svelte";
    import ReferenceSegmentationPanel from "./ReferenceSegmentationPanel.svelte";
    import {
        getSegmentationKey,
        type Segmentation,
    } from "./segmentationContext.svelte";
    import { representationLetter } from "./segmentationUtils";
    import ThresholdSlider from "./ThresholdSlider.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const segmentationContext = mainViewerContext.segmentationContext;

    interface Props {
        segmentation: Segmentation;
        /** Show this slice's area under the row. */
        showArea: boolean;
        /** Delete asks first; the section owns the modal, because a delete unmounts the row. */
        ondelete: (segmentation: Segmentation) => void;
    }

    let { segmentation, showArea, ondelete }: Props = $props();
    const uid = $props.id();

    const feature = segmentation.feature;
    const dataRepresentation = segmentation.data_representation;
    const isMulti =
        dataRepresentation == "MultiLabel" ||
        dataRepresentation == "MultiClass";
    const image = viewerContext.image;

    const visible = $derived(
        segmentationContext.shownSegmentations.has(
            getSegmentationKey(segmentation),
        ),
    );

    // Must not run inside $derived: getOrCreateSegmentationItem mutates the image cache.
    const segmentationItem =
        segmentationContext.getSegmentationItem(segmentation);

    const segmentationState = $derived(
        segmentationItem.getSegmentationState(viewerContext.index),
    );
    const isEditable = globalContext.canEdit(segmentation);
    const isEmptyForCurrentSlice = $derived(
        segmentationItem.isEmptyForSlice(viewerContext.index),
    );
    let duplicateOpen = $state(false);

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

    const hasReferenceMask = $derived(
        segmentation.annotation_type === "grader_segmentation" &&
            Boolean(segmentation.reference_segmentation_id),
    );
    const maskingApplied = $derived(
        mainViewerContext.isMaskingApplied(segmentation),
    );

    function pointerEnter() {
        mainViewerContext.highlightedSegmentationItem = segmentationItem;
    }

    function pointerLeave() {
        mainViewerContext.highlightedSegmentationItem = undefined;
    }

    function applyDuplicateAI() {
        duplicate(
            segmentationContext,
            segmentation,
            segmentationItem,
            image,
            viewerContext,
            false,
            "Q",
            segmentationItem.threshold, //original threshold
            0.5, //new threshold
            taskContext,
        );
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
        {#if hasReferenceMask}
            <IconButton
                size="icon-xs"
                label="Mask with reference"
                aria-pressed={maskingApplied}
                data-sticky={maskingApplied}
                class="aria-pressed:bg-background-selected"
                onclick={() =>
                    mainViewerContext.toggleMasking(segmentationItem)}
            >
                <Intersect />
            </IconButton>
        {/if}
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
        {#if isActive && isEditable && segmentationState}
            <SyncStatus sync={segmentationState.syncState} />
        {/if}
        {#if dataRepresentation == "Probability" && isActive}
            <ThresholdSlider {segmentation} {segmentationItem} />
        {/if}
        {#if isActive && segmentation.annotation_type == "model_segmentation"}
            <Button variant="outline" size="sm" onclick={applyDuplicateAI}>
                Duplicate
            </Button>
        {/if}
        {#if showArea && !isMulti}
            <SliceArea {segmentation} {segmentationItem} />
        {/if}
        {#if isMulti}
            <MultiFeatureSelector {segmentation} active={isActive} {showArea} />
        {/if}
        {#if segmentationItem.loading}
            <p class="text-helper-text-01 text-text-secondary">
                Loading segmentation…
            </p>
        {/if}
        {#if isActive && segmentation.annotation_type === "grader_segmentation"}
            <!-- No comment editing: the segmentation tag API keeps no comment. -->
            <div
                class="flex flex-col gap-1"
                role="group"
                aria-labelledby="{uid}-tags"
            >
                <p id="{uid}-tags" class="text-label-01 text-text-secondary">
                    Tags
                </p>
                <Tagger
                    tagType="Segmentation"
                    tags={segmentation.tags}
                    tag={(id) =>
                        tagSegmentation(segmentation as SegmentationGET, id)}
                    untag={(id) =>
                        untagSegmentation(segmentation as SegmentationGET, id)}
                />
            </div>
        {/if}
        {#if isActive}
            {#if segmentation.annotation_type === "grader_segmentation"}
                <ReferenceSegmentationPanel
                    {segmentation}
                    {isEditable}
                    {segmentationItem}
                />
            {/if}
            {#if dataRepresentation == "Binary" || dataRepresentation == "DualBitMask"}
                <CCPanel {segmentationItem} />
            {/if}
            {#if isEditable || segmentationState}
                <div class="flex flex-wrap gap-x-4 pb-2">
                    {#if isEditable}
                        <ImportPanel
                            {segmentation}
                            {image}
                            {segmentationItem}
                        />
                    {/if}
                    {#if segmentationState}
                        <Popover.Root bind:open={duplicateOpen}>
                            <Popover.Trigger>
                                {#snippet child({ props })}
                                    <Button {...props} variant="ghost" size="sm"
                                        >Duplicate…</Button
                                    >
                                {/snippet}
                            </Popover.Trigger>
                            <Popover.Content
                                role="dialog"
                                aria-label="Duplicate"
                                align="start"
                            >
                                <DuplicateAnnotationPanel
                                    {segmentation}
                                    {image}
                                    {segmentationItem}
                                    oncreate={() => (duplicateOpen = false)}
                                />
                            </Popover.Content>
                        </Popover.Root>
                    {/if}
                </div>
            {/if}
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
