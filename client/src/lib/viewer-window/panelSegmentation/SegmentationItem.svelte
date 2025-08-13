<script lang="ts">
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import { Hide, PanelIcon, Show, Trash } from "../icons/icons";
    import ThresholdSlider from "./ThresholdSlider.svelte";

    import CCPanel from "./CCPanel.svelte";
    import DuplicateAnnotationPanel from "./DuplicateAnnotationPanel.svelte";
    import FeatureColorPicker from "./FeatureColorPicker.svelte";
    import ImportPanel from "./ImportPanel.svelte";
    import MultiFeatureSelector from "./MultiFeatureSelector.svelte";
    import ReferenceSegmentationPanel from "./ReferenceSegmentationPanel.svelte";
    import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
    import StringDialogue from "$lib/StringDialogue.svelte";
    import AI from "../icons/AI.svelte";
    import { duplicate } from "./duplicate_utils";

    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        segmentation: Segmentation;
        style?: "AI" | "normal";
    }

    let { segmentation, style = "normal" }: Props = $props();
    const { feature, dataRepresentation } = segmentation;

    const viewerContext = getContext<ViewerContext>("viewerContext");

    const image = viewerContext.image;
    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );

    const { segmentationContext } = segmentationOverlay;
    segmentationContext.visibleSegmentations.add(segmentation);

    const segmentationItem = image.getSegmentationItem(segmentation);
    let segmentationState = $derived(
        segmentationItem.getSegmentationState(viewerContext.index),
    );

    async function removeAnnotation() {
        const resolve = () => {
            // remove from database on server
            segmentation.delete();
            segmentationContext.toggleActive(undefined);
            segmentationItem.dispose();
        };

        globalContext.dialogue = {
            component: StringDialogue,
            props: {
                query: `Delete segmentation [${segmentation.id}]?`,
                approve: "Delete",
                decline: "Cancel",
                resolve,
            },
        };
    }

    function toggleShow() {
        segmentationContext.toggleShow(segmentation);
    }

    function showOnly() {
        segmentationContext.showOnly(segmentation);
    }

    const isEditable = globalContext.canEdit(segmentation);
    function activate() {
        segmentationContext.toggleActive(segmentationItem);
    }

    let active = $derived(
        segmentationContext.segmentationItem == segmentationItem,
    );

    let collapsed = $state(true);

    function pointerEnter() {
        segmentationOverlay.highlightedSegmentationItem = segmentationItem;
    }

    function pointerLeave() {
        segmentationOverlay.highlightedSegmentationItem = undefined;
    }

    const segmentationType = {
        Binary: "B",
        DualBitMask: "Q",
        Probability: "P",
        MultiClass: "MC",
        MultiLabel: "ML",
    }[segmentation.dataRepresentation];

    function applyDuplicate() {
        duplicate(
            globalContext,
            segmentation,
            segmentationItem,
            image,
            viewerContext,
            false,
            "Q",
            globalContext.creator,
        );
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="content"
    class:compact={style == "AI"}
    class:normal={style == "normal"}
    class:active
    onpointerenter={pointerEnter}
    onpointerleave={pointerLeave}
>
    <div class="row">
        <div>
            {#if segmentationContext.visibleSegmentations.has(segmentation)}
                <PanelIcon
                    onclick={toggleShow}
                    onrightclick={showOnly}
                    tooltip="Hide"
                    Icon={Show}
                />
            {:else}
                <PanelIcon
                    onclick={toggleShow}
                    onrightclick={showOnly}
                    tooltip="Show"
                    Icon={Hide}
                />
            {/if}
        </div>

        {#if !(dataRepresentation == "MultiLabel" || dataRepresentation == "MultiClass")}
            <FeatureColorPicker {segmentation} />
        {/if}

        <div class="expand" onclick={activate}>
            {#if style == "AI"}
                <div class="ai"><AI size="1.2em" /></div>
            {/if}
            <div class="feature-name">{feature.name}</div>
            <div class="segmentationID">[{segmentation.id}]</div>
            <div class="segmentationType">[{segmentationType}]</div>
        </div>

        {#if isEditable}
            <PanelIcon
                onclick={removeAnnotation}
                tooltip="Delete"
                Icon={Trash}
            />
        {/if}
    </div>

    {#if dataRepresentation == "Probability"}
        {#if active}
            <div class="row">
                <ThresholdSlider {segmentation} />
            </div>
        {/if}
    {/if}
    {#if active && style == "AI"}
        <div class="row">
            <button onclick={applyDuplicate}>Duplicate</button>
        </div>
    {/if}

    {#if dataRepresentation == "MultiLabel" || dataRepresentation == "MultiClass"}
        <MultiFeatureSelector {segmentation} {active} />
    {/if}
    {#if active}
        <div class="open" onclick={() => (collapsed = !collapsed)}>
            {#if collapsed}
                &#9654;
            {:else}
                &#9660;
            {/if}
        </div>

        {#if !collapsed}
            <div class="content">
                {#if isEditable}
                    <div class="row">
                        <ImportPanel
                            {segmentation}
                            {image}
                            {segmentationItem}
                        />
                    </div>
                {/if}
                <div class="row">
                    {#if segmentationState}
                        <DuplicateAnnotationPanel
                            {segmentation}
                            {image}
                            {segmentationItem}
                        />
                    {/if}
                </div>

                <div class="row">
                    <ReferenceSegmentationPanel
                        {segmentation}
                        {image}
                        {isEditable}
                        {segmentationItem}
                    />
                </div>

                {#if dataRepresentation == "Binary" || dataRepresentation == "DualBitMask"}
                    <div class="row">
                        <CCPanel {segmentationItem} />
                    </div>
                {/if}
            </div>
        {/if}
    {/if}
</div>

<style>
    div {
        display: flex;
    }
    div.content.compact {
        padding: 0em;
    }
    div.ai {
        align-items: center;
        padding-right: 0.2em;
    }
    div.content.normal {
        padding: 0.2em;
        border-radius: 2px;
    }
    div.content {
        flex-direction: column;
    }
    div.content.active {
        /* border: 1px solid rgba(100, 255, 255, 0.3); */
    }
    div.row {
        flex-direction: row;
        flex: 1;
        width: 100%;
    }
    div.open {
        border-top: 1px solid rgba(100, 255, 255, 0.3);
        flex-direction: row;
        flex: 1;
        cursor: pointer;
    }
    div.open:hover {
        background-color: rgba(100, 255, 255, 0.3);
    }

    div.expand {
        cursor: pointer;
        flex: 1;
        min-height: 2em;
        border-radius: 2px;
        transition: all 0.3s ease;
    }
    div.active {
        background-color: rgba(100, 255, 255, 0.3);
    }
    div.expand:hover {
        background-color: rgba(100, 255, 255, 0.3);
    }
    div.feature-name {
        flex: 1;
        /* max-width: 12em; */
        padding-right: 0.5em;
    }
    div.segmentationID {
        font-size: x-small;
        flex: 0;
    }
    div.feature-name,
    div.segmentationID,
    div.segmentationType {
        align-items: center;
    }
</style>
