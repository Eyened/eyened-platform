<script lang="ts">
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { Annotation } from "$lib/datamodel/annotation.svelte";
    import { dialogueManager } from "$lib/dialogue/DialogueManager";
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
    import ReferenceAnnotationPanel from "./ReferenceAnnotationPanel.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    interface Props {
        annotation: Annotation;
    }

    let { annotation }: Props = $props();
    const { feature, annotationType } = annotation;

    const viewerContext = getContext<ViewerContext>("viewerContext");

    const image = viewerContext.image;
    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const { segmentationContext } = segmentationOverlay;

    const segmentationItem = image.getSegmentationItem(annotation);

    async function removeAnnotation() {
        const resolve = () => {
            annotation.annotationData.forEach$((annotationData) =>
                annotationData.delete(false),
            );
            // remove from database on server
            annotation.delete();
            segmentationContext.toggleActive(undefined);
            segmentationItem?.dispose();
        };

        dialogueManager.showQuery(
            `Delete annotation [${annotation.id}]?`,
            "Delete",
            "Cancel",
            resolve,
        );
    }

    function toggleShow() {
        segmentationContext.toggleShow(annotation);
    }

    const isEditable = globalContext.canEdit(annotation);
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
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="content"
    class:active
    onpointerenter={pointerEnter}
    onpointerleave={pointerLeave}
>
    <div class="row">
        <div>
            {#if segmentationContext.hideAnnotations.has(annotation)}
                <PanelIcon onclick={toggleShow} tooltip="Show" Icon={Hide} />
            {:else}
                <PanelIcon onclick={toggleShow} tooltip="Hide" Icon={Show} />
            {/if}
        </div>

        {#if !(annotationType.dataRepresentation == "MultiLabel" || annotationType.dataRepresentation == "MultiClass")}
            <FeatureColorPicker {annotation} />
        {/if}

        <div class="expand" onclick={activate}>
            <div class="feature-name">{feature.name}</div>
            <div class="annotationID">[{annotation.id}]</div>
        </div>

        {#if isEditable}
            <PanelIcon
                onclick={removeAnnotation}
                tooltip="Delete"
                Icon={Trash}
            />
        {/if}
    </div>
    {#if active}
        {#if annotationType.dataRepresentation == "Probability"}
            <div class="row">
                <ThresholdSlider {annotation} />
            </div>
        {/if}

        {#if annotationType.dataRepresentation == "MultiLabel" || annotationType.dataRepresentation == "MultiClass"}
            <MultiFeatureSelector {annotation} />
        {/if}

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
                        <ImportPanel {annotation} {image} {segmentationItem} />
                    </div>
                {/if}
                <div class="row">
                    {#await segmentationItem.getSegmentationState(viewerContext.index) then segmentationState}
                        {#if segmentationState}
                            <DuplicateAnnotationPanel
                                {annotation}
                                {image}
                                {segmentationItem}
                                segmentation={segmentationState.segmentation}
                            />
                        {/if}
                    {/await}
                </div>

                <div class="row">
                    <ReferenceAnnotationPanel
                        {annotation}
                        {image}
                        {isEditable}
                        {segmentationItem}
                    />
                </div>

                {#if annotationType.dataRepresentation == "Binary" || annotationType.dataRepresentation == "DualBitMask"}
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
    div.content {
        flex-direction: column;
        padding: 0.2em;
        border-radius: 2px;
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
        align-items: center;
    }
    div.annotationID {
        font-size: x-small;
        flex: 0;
        align-items: center;
    }
</style>
