<!--
@component
The Selected pane for a segmentation: Duplicate, Duplicate… and Import in the header; color, Threshold, Mask with reference, classes and Area open; Tags, Reference image and Connected components folded.
-->
<script lang="ts">
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { Toggle } from "$lib/components/ui/toggle/index.js";
    import { modelSegmentations, segmentations } from "$lib/data/stores.svelte";
    import { tagSegmentation, untagSegmentation } from "$lib/data/helpers";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import SliceArea from "$lib/layers/SliceArea.svelte";
    import SyncStatus from "$lib/layers/SyncStatus.svelte";
    import { toHex } from "$lib/utils";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import Tagger from "$lib/tags/Tagger.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import CCPanel from "$lib/viewer-window/panelSegmentation/CCPanel.svelte";
    import { duplicate } from "$lib/viewer-window/panelSegmentation/duplicate_utils";
    import DuplicateAnnotationPanel from "$lib/viewer-window/panelSegmentation/DuplicateAnnotationPanel.svelte";
    import FeatureColorPicker from "$lib/viewer-window/panelSegmentation/FeatureColorPicker.svelte";
    import ImportPanel from "$lib/viewer-window/panelSegmentation/ImportPanel.svelte";
    import MultiFeatureSelector from "$lib/viewer-window/panelSegmentation/MultiFeatureSelector.svelte";
    import ReferenceSegmentationPanel from "$lib/viewer-window/panelSegmentation/ReferenceSegmentationPanel.svelte";
    import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
    import { groupTitle } from "$lib/viewer-window/panelSegmentation/segmentationUtils";
    import ThresholdSlider from "$lib/viewer-window/panelSegmentation/ThresholdSlider.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
    import CopyFile from "carbon-icons-svelte/lib/CopyFile.svelte";
    import { getContext, type Snippet } from "svelte";
    import type { SegmentationGET } from "../../../types/openapi_types";
    import PaneHeader from "./PaneHeader.svelte";

    let {
        id,
        item,
        remove,
    }: { id: string; item: SegmentationItem; remove?: Snippet } = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const workspace = getContext<Workspace>("workspace");
    const { segmentationContext } = mainViewerContext;
    const image = viewerContext.image;
    const isModel = $derived(
        item.segmentation.annotation_type === "model_segmentation",
    );
    // The store's record: tag and reference edits replace it, while the item keeps the one it was made from.
    const segmentation: Segmentation = $derived(
        (isModel ? modelSegmentations : segmentations).get(
            item.segmentation.id,
        ) ?? item.segmentation,
    );
    const rep = $derived(item.segmentation.data_representation);
    const isMulti = $derived(rep === "MultiLabel" || rep === "MultiClass");
    const isEditable = $derived(globalContext.canEdit(segmentation));
    const sliceState = $derived(item.getSegmentationState(viewerContext.index));
    let duplicateOpen = $state(false);
    let rare: string[] = $state([]);
    const me = globalContext.user.id;
    // Read once at mount, as the row's picker does, so the derived read below never assigns a colour.
    mainViewerContext.getFeatureColor(item.segmentation);
    const swatch = $derived(
        isMulti
            ? undefined
            : toHex(mainViewerContext.getFeatureColor(item.segmentation)),
    );

    function quickDuplicate() {
        duplicate(
            segmentationContext,
            segmentation,
            item,
            image,
            viewerContext,
            false,
            "Q",
            item.threshold,
            0.5,
            taskContext,
        );
    }
</script>

<PaneHeader
    {id}
    name={segmentation.feature.name}
    type="Segmentation · {groupTitle(segmentation, me)}"
    {swatch}
    {remove}
>
    {#snippet status()}
        {#if isEditable && sliceState}
            <SyncStatus sync={sliceState.syncState} />
        {/if}
    {/snippet}
    {#snippet actions()}
        {#if isModel}
            <IconButton
                size="icon-xs"
                label="Duplicate"
                onclick={quickDuplicate}><Copy /></IconButton
            >
        {/if}
        {#if sliceState}
            <Popover.Root bind:open={duplicateOpen}>
                <Popover.Trigger>
                    {#snippet child({ props })}
                        <IconButton {...props} size="icon-xs" label="Duplicate…"
                            ><CopyFile /></IconButton
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
                        segmentationItem={item}
                        oncreate={() => (duplicateOpen = false)}
                    />
                </Popover.Content>
            </Popover.Root>
        {/if}
        {#if isEditable}
            <ImportPanel {segmentation} {image} segmentationItem={item} />
        {/if}
    {/snippet}
</PaneHeader>
<div class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-4 py-2">
    {#if !isMulti}
        <div class="flex items-center gap-2">
            <span class="text-label-01 text-text-secondary">Color</span>
            <FeatureColorPicker {segmentation} />
        </div>
    {/if}
    {#if rep === "Probability"}
        <ThresholdSlider {segmentation} segmentationItem={item} />
    {/if}
    {#if segmentation.annotation_type === "grader_segmentation" && segmentation.reference_segmentation_id}
        <Field.Field orientation="horizontal" class="w-auto">
            <Toggle
                id="{id}-mask"
                bind:checked={
                    () => mainViewerContext.isMaskingApplied(segmentation),
                    () => mainViewerContext.toggleMasking(item)
                }
            />
            <Field.Label
                for="{id}-mask"
                class="text-body-compact-01 text-text-primary"
                >Mask with reference</Field.Label
            >
        </Field.Field>
    {/if}
    {#if isMulti}
        <div role="group" aria-labelledby="{id}-classes">
            <p id="{id}-classes" class="text-label-01 text-text-secondary">
                Classes
            </p>
            <MultiFeatureSelector
                {segmentation}
                active
                showArea={workspace.layerArea}
            />
        </div>
    {/if}
    {#if workspace.layerArea && !isMulti}
        <SliceArea {segmentation} segmentationItem={item} />
    {/if}
    <Accordion.Root bind:value={rare} class="-mx-4">
        {#if segmentation.annotation_type === "grader_segmentation"}
            <Accordion.Item value="tags">
                <Accordion.Trigger level={4}>Tags</Accordion.Trigger>
                <Accordion.Content>
                    <!-- No comment editing: the segmentation tag API keeps no comment. -->
                    <Tagger
                        tagType="Segmentation"
                        tags={segmentation.tags}
                        tag={(t) =>
                            tagSegmentation(segmentation as SegmentationGET, t)}
                        untag={(t) =>
                            untagSegmentation(
                                segmentation as SegmentationGET,
                                t,
                            )}
                    />
                </Accordion.Content>
            </Accordion.Item>
            <Accordion.Item value="reference">
                <Accordion.Trigger level={4}>Reference image</Accordion.Trigger>
                <Accordion.Content>
                    <ReferenceSegmentationPanel
                        {segmentation}
                        {isEditable}
                        segmentationItem={item}
                    />
                </Accordion.Content>
            </Accordion.Item>
        {/if}
        {#if rep === "Binary" || rep === "DualBitMask"}
            <Accordion.Item value="components">
                <Accordion.Trigger level={4}
                    >Connected components</Accordion.Trigger
                >
                <Accordion.Content
                    ><CCPanel segmentationItem={item} /></Accordion.Content
                >
            </Accordion.Item>
        {/if}
    </Accordion.Root>
</div>
