<!--
@component
The Selected pane for a segmentation: Duplicate and Import in the header; color, Threshold, Mask with reference, classes and Area open; Tags, Reference image and Connected components folded.
-->
<script lang="ts">
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Toggle } from "$lib/components/ui/toggle/index.js";
    import { modelSegmentations, segmentations } from "$lib/data/stores.svelte";
    import { tagSegmentation, untagSegmentation } from "$lib/data/helpers";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import SliceArea from "$lib/layers/SliceArea.svelte";
    import SyncStatus from "$lib/layers/SyncStatus.svelte";
    import { worstState } from "$lib/saving/saveTracker.svelte";
    import { segmentationSavers } from "$lib/saving/thresholdSavers";
    import { toHex } from "$lib/utils";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import Tagger from "$lib/tags/Tagger.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import CCPanel from "$lib/viewer-window/panelSegmentation/CCPanel.svelte";
    import { duplicate } from "$lib/viewer-window/panelSegmentation/duplicate_utils";
    import FeatureColorPicker from "$lib/viewer-window/panelSegmentation/FeatureColorPicker.svelte";
    import ImportPanel from "$lib/viewer-window/panelSegmentation/ImportPanel.svelte";
    import MultiFeatureSelector from "$lib/viewer-window/panelSegmentation/MultiFeatureSelector.svelte";
    import ReferenceSegmentationPanel from "$lib/viewer-window/panelSegmentation/ReferenceSegmentationPanel.svelte";
    import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
    import {
        authorName,
        groupTitle,
    } from "$lib/viewer-window/panelSegmentation/segmentationUtils";
    import ThresholdSlider from "$lib/viewer-window/panelSegmentation/ThresholdSlider.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import { DropdownMenu } from "bits-ui";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
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
    // The worst of all its B-scans and its threshold, not only the shown B-scan; Retry sends them all.
    const savers = $derived(segmentationSavers(item));
    const saveState = $derived(worstState(savers));
    function retry() {
        for (const saver of savers) void saver.flush();
    }
    let rare: string[] = $state([]);
    const me = globalContext.user.id;
    // Read once at mount, as the row's picker does, so the derived read below never assigns a colour.
    mainViewerContext.getFeatureColor(item.segmentation);
    const swatch = $derived(
        isMulti
            ? undefined
            : toHex(mainViewerContext.getFeatureColor(item.segmentation)),
    );
    const hasMask = $derived(
        segmentation.annotation_type === "grader_segmentation" &&
            !!segmentation.reference_segmentation_id,
    );
    const appearance = $derived(!isMulti || rep === "Probability" || hasMask);
    // The reference's feature and author, as Reference image shows it, for the folded title.
    const referenceSummary = $derived.by(() => {
        if (segmentation.annotation_type !== "grader_segmentation")
            return undefined;
        const referenceId = segmentation.reference_segmentation_id ?? null;
        if (referenceId === null) return "None";
        const reference = segmentations.get(referenceId);
        return reference
            ? `${reference.feature.name} · ${authorName(reference, me)}`
            : `[${referenceId}]`;
    });

    // MultiClass and MultiLabel copies keep their type, so the letter is unused there.
    function copy(volume: boolean, type: "Q" | "B" | "P") {
        duplicate(
            segmentationContext,
            segmentation,
            item,
            image,
            viewerContext,
            volume,
            type,
            item.threshold ?? segmentation.threshold ?? 0.5, // original threshold
            0.5, // new threshold
            taskContext,
        );
    }
    const asTypes = [
        { type: "Q", label: "As Questionable" },
        { type: "B", label: "As Binary" },
        { type: "P", label: "As Probability" },
    ] as const;
    // Carbon Menu items, styled as the combo button's.
    const menuItem =
        "flex h-8 cursor-pointer items-center px-4 text-body-compact-01 text-text-secondary outline-none select-none hover:bg-layer-hover-01 hover:text-text-primary data-highlighted:bg-layer-hover-01 data-highlighted:text-text-primary data-highlighted:outline-2 data-highlighted:-outline-offset-2 data-highlighted:outline-focus";
    const groupHeading =
        "flex h-8 items-center px-4 text-label-01 text-text-secondary";
</script>

<PaneHeader
    {id}
    name={segmentation.feature.name}
    type="Segmentation · {groupTitle(segmentation, me)}"
    {swatch}
    {remove}
>
    {#snippet status()}
        {#if isEditable && savers.length > 0}
            <SyncStatus sync={saveState} onretry={retry} />
        {/if}
    {/snippet}
    {#snippet actions()}
        <!-- ASSUMPTION: shown where either of the old Duplicate buttons showed (AI rows, or a loaded B-scan). -->
        {#if isModel || sliceState}
            {#if isMulti && !image.is3D}
                <IconButton
                    size="icon-xs"
                    label="Duplicate"
                    onclick={() => copy(false, "Q")}><Copy /></IconButton
                >
            {:else}
                <DropdownMenu.Root>
                    <DropdownMenu.Trigger>
                        {#snippet child({ props })}
                            <IconButton
                                {...props}
                                size="icon-xs"
                                label="Duplicate"><Copy /></IconButton
                            >
                        {/snippet}
                    </DropdownMenu.Trigger>
                    <DropdownMenu.Portal>
                        <DropdownMenu.Content
                            align="start"
                            sideOffset={0}
                            class="z-50 w-60 bg-layer-01 py-1 shadow-popover outline-none"
                        >
                            {#if isMulti}
                                <DropdownMenu.Item
                                    class={menuItem}
                                    onSelect={() => copy(false, "Q")}
                                    >This B-scan</DropdownMenu.Item
                                >
                                <DropdownMenu.Item
                                    class={menuItem}
                                    onSelect={() => copy(true, "Q")}
                                    >Volume</DropdownMenu.Item
                                >
                            {:else if image.is3D}
                                {#each [{ volume: false, heading: "This B-scan" }, { volume: true, heading: "Volume" }] as group, i (group.heading)}
                                    {#if i > 0}
                                        <DropdownMenu.Separator
                                            class="my-1 h-px bg-border-subtle-01"
                                        />
                                    {/if}
                                    <DropdownMenu.Group>
                                        <DropdownMenu.GroupHeading
                                            class={groupHeading}
                                            >{group.heading}</DropdownMenu.GroupHeading
                                        >
                                        {#each asTypes as t (t.type)}
                                            <DropdownMenu.Item
                                                class={menuItem}
                                                onSelect={() =>
                                                    copy(group.volume, t.type)}
                                                >{t.label}</DropdownMenu.Item
                                            >
                                        {/each}
                                    </DropdownMenu.Group>
                                {/each}
                            {:else}
                                {#each asTypes as t (t.type)}
                                    <DropdownMenu.Item
                                        class={menuItem}
                                        onSelect={() => copy(false, t.type)}
                                        >{t.label}</DropdownMenu.Item
                                    >
                                {/each}
                            {/if}
                        </DropdownMenu.Content>
                    </DropdownMenu.Portal>
                </DropdownMenu.Root>
            {/if}
        {/if}
        {#if isEditable}
            <ImportPanel {segmentation} {image} segmentationItem={item} />
        {/if}
    {/snippet}
</PaneHeader>
<div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-3">
    {#if appearance}
        <section aria-labelledby="{id}-appearance" class="flex flex-col gap-4">
            <h4
                id="{id}-appearance"
                class="text-heading-compact-01 text-text-primary"
            >
                Appearance
            </h4>
            {#if !isMulti}
                <div class="flex flex-col items-start gap-2">
                    <span class="text-label-01 text-text-secondary">Color</span>
                    <FeatureColorPicker {segmentation} />
                </div>
            {/if}
            {#if rep === "Probability"}
                <ThresholdSlider {segmentation} segmentationItem={item} />
            {/if}
            {#if hasMask}
                <Field.Field orientation="vertical" class="w-auto">
                    <Field.Label
                        for="{id}-mask"
                        class="text-label-01 text-text-secondary"
                        >Mask with reference</Field.Label
                    >
                    <div class="flex items-center gap-2">
                        <Toggle
                            id="{id}-mask"
                            stateText
                            bind:checked={
                                () =>
                                    mainViewerContext.isMaskingApplied(
                                        segmentation,
                                    ),
                                () => mainViewerContext.toggleMasking(item)
                            }
                        />
                    </div>
                </Field.Field>
            {/if}
        </section>
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
                <Accordion.Trigger
                    level={4}
                    summary={segmentation.tags.length
                        ? String(segmentation.tags.length)
                        : undefined}>Tags</Accordion.Trigger
                >
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
                <Accordion.Trigger level={4} summary={referenceSummary}
                    >Reference image</Accordion.Trigger
                >
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
