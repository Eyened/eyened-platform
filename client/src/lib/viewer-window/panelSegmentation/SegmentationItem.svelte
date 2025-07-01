<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onMount } from "svelte";
    import {
        Duplicate,
        Hide,
        ImportSegmentation,
        PanelIcon,
        Show,
        Trash,
    } from "../icons/icons";
    import FeatureColorPicker from "./FeatureColorPicker.svelte";
    import SegmentationTools from "./SegmentationTools.svelte";
    import ImportSegmentationSelector from "./ImportSegmentationSelector.svelte";
    import BscanLinks from "./BscanLinks.svelte";
    import ConnectedComponents from "../icons/ConnectedComponents.svelte";
    import { Annotation } from "$lib/datamodel/annotation.svelte";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import {} from "./segmentationUtils";
    import { data } from "$lib/datamodel/model";
    import ThresholdSlider from "./ThresholdSlider.svelte";
    import {
        BinarySegmentation,
        ProbabilitySegmentation,
    } from "$lib/webgl/segmentation";
    import { SegmentationState } from "$lib/webgl/segmentationState";
    import Intersection from "../icons/Intersection.svelte";
    import ReferenceAnnotationSelector from "./ReferenceAnnotationSelector.svelte";
    import { dialogueManager } from "$lib/dialogue/DialogueManager";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import MultiFeatureSelector from "./MultiFeatureSelector.svelte";
    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        annotation: Annotation;
    }

    let { annotation }: Props = $props();
    const { annotationData, feature, annotationType } = annotation;
    const { creator } = globalContext;

    const viewerContext = getContext<ViewerContext>("viewerContext");

    const image = viewerContext.image;
    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const { segmentationContext } = segmentationOverlay;

    const segmentationItem = image.getSegmentationItem(annotation);

    let segmentationState = $state<SegmentationState | undefined>(undefined);
    let segmentation = $derived(segmentationState?.segmentation);

    let activeIndex = $state<number | number[]>(0);

    onMount(async () => {
        segmentationState = await segmentationItem.getSegmentationState(
            viewerContext.index,
        );
    });

    const isEditable = globalContext.canEdit(annotation);

    let active = $derived(
        segmentationContext.activeAnnotationID == annotation.id,
    );

    function activate() {
        segmentationContext.toggleActive(annotation);
    }

    function toggleShow() {
        segmentationContext.toggleShow(annotation);
    }

    async function removeAnnotation() {
        const resolve = () => {
            annotation.annotationData.forEach$((annotationData) =>
                annotationData.delete(false),
            );
            // remove from database on server
            annotation.delete();
            segmentationContext.activeAnnotationID = undefined;
            segmentationItem?.dispose();
        };

        dialogueManager.showQuery(
            `Delete annotation [${annotation.id}]?`,
            "Delete",
            "Cancel",
            resolve,
        );
    }

    async function duplicate(type?: string) {
        dialogueManager.showQuery(`Duplicating annotation ${annotation.id}...`);

        // always duplicate as RG_MASK
        const rgMaskAnnotationType = data.annotationTypes.find(
            (a) => a.name == "R/G mask" && a.dataRepresentation == "RG_MASK",
        );

        const item = {
            ...annotation,
            annotationReferenceId: annotation.annotationReferenceId,
            annotationTypeId: rgMaskAnnotationType!.id,
            creatorId: creator.id,
        };

        const newAnnotation = await Annotation.create(item);

        const newSegmentationItem = image.getSegmentationItem(newAnnotation);
        const scanNr = viewerContext.index;
        await newSegmentationItem.importOther(scanNr, segmentation!);

        dialogueManager.hide();
    }

    function setAnnotationReference() {
        dialogueManager.show(
            ReferenceAnnotationSelector,
            {
                annotation,
                image,
            },
            (other: Annotation) => {
                annotation.update({
                    annotationReferenceId: other.id,
                });
            },
        );
    }

    async function importFromOther() {
        dialogueManager.show(
            ImportSegmentationSelector,
            {
                annotation,
                image,
            },
            (other: Annotation) => {
                const otherSegmentation = image
                    .getSegmentationItem(other)
                    ?.getSegmentation(viewerContext.index);
                if (otherSegmentation) {
                    segmentationItem?.importOther(
                        viewerContext.index,
                        otherSegmentation,
                    );
                } else {
                    console.warn(
                        "Import from other: no segmentation found for annotation",
                        other.id,
                    );
                }
            },
        );
    }

    function removeReference() {
        annotation.update({ annotationReferenceId: null });
    }

    let notOnBscan = $derived.by(() => {
        if (active) {
            return false;
        }
        if (annotationType.name == "Segmentation OCT Volume") {
            return false;
        } else {
            for (const a of $annotationData) {
                if (a.scanNr == viewerContext.index) {
                    return false;
                }
            }
            return true;
        }
    });

    let connectedComponentsActive = $derived(
        segmentationOverlay.applyConnectedComponents.has(segmentationItem),
    );
    function toggleConnectedComponents() {
        segmentationOverlay.toggleConnectedComponents(segmentationItem);
    }

    function toggleApplyMask() {
        segmentationOverlay.toggleMasking(segmentationItem);
    }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
    class="main"
    class:active
    class:notOnBscan
    onmouseenter={() =>
        (segmentationOverlay.highlightedSegmentationItem = segmentationItem)}
    onmouseleave={() =>
        (segmentationOverlay.highlightedSegmentationItem = undefined)}
>
    {#if active && image.is3D && annotationType.name != "Segmentation OCT Volume" && segmentation}
        <BscanLinks {annotation} {segmentation} />
    {/if}
    <div class="row">
        {#if (segmentation && segmentation instanceof BinarySegmentation) || segmentation instanceof ProbabilitySegmentation}
            <FeatureColorPicker {annotation} />
        {/if}

        <div>
            {#if segmentationContext.hideAnnotations.has(annotation)}
                <PanelIcon onclick={toggleShow} tooltip="Show" Icon={Hide} />
            {:else}
                <PanelIcon onclick={toggleShow} tooltip="Hide" Icon={Show} />
            {/if}
        </div>

        <div class="expand" onclick={activate}>
            <div class="feature-name">{feature.name}</div>
            <div class="annotationID">
                {annotation.id}
            </div>
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
        <div class="row">
            {#if segmentationItem && isEditable}
                <SegmentationTools {segmentationItem} {activeIndex} />
            {/if}
        </div>
        {#if segmentation instanceof ProbabilitySegmentation}
            <div class="row">
                <ThresholdSlider {annotation} />
            </div>
        {/if}
        <div class="row">
            <PanelIcon
                onclick={() => duplicate("R/G mask")}
                tooltip="Duplicate"
                Icon={Duplicate}
            />

            {#if segmentation instanceof ProbabilitySegmentation}
                <PanelIcon
                    onclick={() => duplicate("Probability")}
                    tooltip="Duplicate Probability"
                    Icon={Duplicate}
                />
            {/if}
            {#if isEditable}
                <PanelIcon
                    onclick={importFromOther}
                    tooltip="Import from other"
                    Icon={ImportSegmentation}
                />
            {/if}
        </div>
        <div class="row">
            {#if !(annotation.annotationType.dataRepresentation == "MULTI_LABEL" || annotation.annotationType.dataRepresentation == "MULTI_CLASS")}
                <PanelIcon
                    onclick={setAnnotationReference}
                    tooltip="Choose reference mask"
                    Icon={Intersection}
                />
            {/if}

            {#if annotation.annotationReferenceId}
                <span
                    class="reference-annotation"
                    onclick={() => removeReference()}
                >
                    [{annotation.annotationReferenceId}]
                </span>
                {#if segmentationOverlay.applyMasking.has(segmentationItem)}
                    <PanelIcon
                        onclick={toggleApplyMask}
                        tooltip="Show"
                        Icon={Hide}
                    />
                {:else}
                    <PanelIcon
                        onclick={toggleApplyMask}
                        tooltip="Hide"
                        Icon={Show}
                    />
                {/if}
            {/if}
        </div>
        {#if segmentation instanceof BinarySegmentation}
            <div class="row">
                <PanelIcon
                    active={connectedComponentsActive}
                    onclick={toggleConnectedComponents}
                    tooltip={(connectedComponentsActive ? "Hide" : "Show") +
                        " connected components"}
                    Icon={ConnectedComponents}
                />
            </div>
        {/if}
        {#if annotation.annotationType.dataRepresentation == "MULTI_LABEL" || annotation.annotationType.dataRepresentation == "MULTI_CLASS"}
            <MultiFeatureSelector {annotation} bind:activeIndex />
        {/if}
    {/if}
</div>

<style>
    div {
        display: flex;
        align-items: center;
    }
    div.notOnBscan {
        opacity: 0.2;
    }
    div.main {
        flex-direction: column;
        border-left: 2px solid rgba(255, 255, 255, 0);
    }
    div.main.active {
        border-radius: 2px;
        background-color: rgba(100, 255, 255, 0.3);
        border-left: 2px solid white;
    }
    div.row {
        flex-direction: row;
        flex: 1;
        width: 100%;
    }
    div.expand {
        cursor: pointer;
        flex: 1;
        min-height: 2em;
        border-radius: 2px;
        transition: all 0.3s ease;
    }
    div.expand:hover {
        background-color: rgba(100, 255, 255, 0.3);
    }
    div.feature-name {
        flex: 1;
        /* max-width: 12em; */
        padding-right: 0.5em;
    }
    div.annotationID {
        font-size: x-small;
        align-items: end;
        flex: 0;
    }
    span.reference-annotation {
        font-size: xx-small;
        opacity: 0.5;
        cursor: pointer;
    }
    span.reference-annotation:hover {
        opacity: 1;
    }
</style>
