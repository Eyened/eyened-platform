<!--
@component
One segmentation row in Layers: eye (right-click shows only this), Mask with reference, colour, the name (sets or unsets the current row), the type badge and Delete.
Under it: the current row's save state, this slice's area, then the row's details.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
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
    let collapsed = $state(true);

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

    const segmentationType = {
        Binary: "B",
        DualBitMask: "Q",
        Probability: "P",
        MultiClass: "MC",
        MultiLabel: "ML",
    }[dataRepresentation];

    function applyDuplicateAI() {
        duplicate(
            globalContext,
            segmentation,
            segmentationItem,
            image,
            viewerContext,
            false,
            "Q",
            segmentationItem.threshold ?? segmentation.threshold ?? 0.5, //original threshold
            0.5, //new threshold
            taskContext,
        );
    }
</script>

<div
    class="segmentation"
    role="group"
    aria-label="{feature.name} segmentation [{segmentation.id}]"
    class:loading={segmentationItem.loading}
    class:current={isActive}
    class:visible
    class:empty-non-editable={!isEditable && isEmptyForCurrentSlice}
    class:empty-editable={isEditable && isEmptyForCurrentSlice}
    onpointerenter={pointerEnter}
    onpointerleave={pointerLeave}
>
    <div class="flex items-start gap-1 py-1 ps-7 pe-2">
        <IconButton
            size="icon-xs"
            label={visible ? "Hide" : "Show"}
            onclick={() =>
                segmentationContext.toggleShowSegmentation(segmentation)}
            oncontextmenu={showOnly}
        >
            {#if visible}<View />{:else}<ViewOff />{/if}
        </IconButton>
        {#if hasReferenceMask}
            <IconButton
                size="icon-xs"
                label="Mask with reference"
                aria-pressed={maskingApplied}
                class="aria-pressed:bg-background-selected"
                onclick={() =>
                    mainViewerContext.toggleMasking(segmentationItem)}
            >
                <Intersect />
            </IconButton>
        {/if}
        {#if !isMulti}
            <FeatureColorPicker {segmentation} />
        {/if}
        <button
            type="button"
            class="name text-body-compact-01"
            aria-pressed={isActive}
            onclick={toggleActive}>{feature.name}</button
        >
        <Tag>{segmentationType}</Tag>
        {#if isEditable}
            <IconButton
                size="icon-xs"
                label="Delete"
                onclick={() => ondelete(segmentation)}
            >
                <TrashCan />
            </IconButton>
        {/if}
    </div>
    <div class="details">
        {#if isActive && isEditable && segmentationState}
            <SyncStatus sync={segmentationState.syncState} />
        {/if}
        {#if showArea && !isMulti}
            <SliceArea {segmentation} {segmentationItem} />
        {/if}
        {#if dataRepresentation == "Probability" && isActive}
            <ThresholdSlider {segmentation} {segmentationItem} />
        {/if}
        {#if isActive && segmentation.annotation_type == "model_segmentation"}
            <Button variant="outline" size="sm" onclick={applyDuplicateAI}>
                Duplicate
            </Button>
        {/if}
        {#if isMulti}
            <MultiFeatureSelector {segmentation} active={isActive} />
        {/if}
        {#if segmentationItem.loading}
            <p class="text-helper-text-01 text-text-secondary">
                Loading segmentation…
            </p>
        {/if}
        {#if isActive}
            <button
                type="button"
                class="more text-body-compact-01"
                aria-expanded={!collapsed}
                onclick={() => (collapsed = !collapsed)}>More</button
            >
            {#if !collapsed}
                {#if isEditable}
                    <ImportPanel {segmentation} {image} {segmentationItem} />
                {/if}
                {#if segmentationState}
                    <DuplicateAnnotationPanel
                        {segmentation}
                        {image}
                        {segmentationItem}
                    />
                {/if}
                {#if segmentation.annotation_type === "grader_segmentation"}
                    <ReferenceSegmentationPanel
                        {segmentation}
                        {image}
                        {isEditable}
                        {segmentationItem}
                    />
                {/if}
                {#if dataRepresentation == "Binary" || dataRepresentation == "DualBitMask"}
                    <CCPanel {segmentationItem} />
                {/if}
            {/if}
        {/if}
    </div>
</div>

<style>
    .segmentation {
        display: flex;
        flex-direction: column;
        border-inline-start: 3px solid transparent;
    }
    .segmentation.visible {
        border-inline-start-color: var(--color-border-strong-01);
    }
    .segmentation.current {
        border-inline-start-color: var(--color-border-interactive);
        background: var(--color-layer-selected-01);
    }
    .segmentation.loading {
        opacity: 0.5;
    }
    .segmentation.empty-non-editable {
        opacity: 0.6;
    }
    .segmentation.empty-editable:not(.current) {
        background: var(--color-layer-hover-01);
    }
    /* The name wraps; no ellipsis, no tooltip. */
    .name,
    .more {
        min-height: 1.5rem;
        padding-inline: 0.25rem;
        border: 0;
        background: transparent;
        color: var(--color-text-primary);
        text-align: start;
        cursor: pointer;
    }
    .name {
        flex: 1;
        min-width: 0;
        overflow-wrap: anywhere;
    }
    .name:hover,
    .more:hover {
        background: var(--color-layer-hover-01);
    }
    .name:focus-visible,
    .more:focus-visible {
        outline: 2px solid var(--color-focus);
        outline-offset: -2px;
    }
    .details {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0.25rem;
        padding-inline: 3.5rem 0.5rem;
    }
    .details:empty {
        display: none;
    }
</style>
