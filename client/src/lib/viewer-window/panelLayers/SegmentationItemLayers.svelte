<!--
	Similar to panelSegmentation / SegmentationItem, but for layers
	Should perhaps be merged in a common component
-->
<script lang="ts">
    import type { DialogueType } from "$lib/types";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onDestroy } from "svelte";
    import { Duplicate, Hide, PanelIcon, Show, Trash } from "../icons/icons";
    import ImportSegmentationSelector from "../panelSegmentation/ImportSegmentationSelector.svelte";
    import LayerThicknessSelector from "./LayerThicknessSelector.svelte";

    import type { Annotation } from "$lib/datamodel/annotation.svelte";
    import { LayerSegmentationOverlay } from "$lib/viewer/overlays/LayerSegmentationOverlay.svelte";
    import { type Writable } from "svelte/store";
    import BscanLinks from "../panelSegmentation/BscanLinks.svelte";
    import SegmentationTools from "../panelSegmentation/SegmentationTools.svelte";
    import {
        deleteAnnotation,
        macularLayers,
    } from "../panelSegmentation/segmentationUtils";

    import { data } from "$lib/datamodel/model";
    import ImportSegmentation from "../icons/ImportSegmentation.svelte";

    import {
        MulticlassSegmentation,
        MultilabelSegmentation,
    } from "$lib/webgl/layerSegmentation";
    import type { SegmentationContext } from "../panelSegmentation/segmentationContext.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

    const globalContext = getContext<GlobalContext>('globalContext');

    interface Props {
        annotation: Annotation;
    }

    let { annotation }: Props = $props();

    const { annotationType, feature } = annotation;
    const segmentationContext = getContext<SegmentationContext>(
        "segmentationContext",
    );
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { creator } = globalContext;
    const { image, registration } = viewerContext;
    const { segmentationController } = image;

    // Note: segmentation is never removed (may cause memory issues in some scenarios)
    const segmentationItem =
        segmentationController.getSegmentationItem(annotation);
    const segmentation = segmentationItem.segmentation as
        | MulticlassSegmentation
        | MultilabelSegmentation;
    const shaders = image.webgl.shaders;
    const layerSegmentationOverlay = new LayerSegmentationOverlay(
        registration,
        segmentation,
        segmentationContext,
        shaders,
    );

    onDestroy(viewerContext.addOverlay(layerSegmentationOverlay));

    let active = $derived(
        segmentationContext.activeAnnotation == segmentation,
    );

    //TODO: fix
    const isEditable = creator == annotation.creator;

    const dialogue = getContext<Writable<DialogueType>>("dialogue");

    function removeAnnotation() {
        deleteAnnotation(dialogue, annotation, () =>
            segmentationController.removeAnnotation(annotation),
        );
    }

    function getNewAnnotation(interpretation: string) {
        // new annotation is always on OCT B-scan (not volume)
        const annotationType = data.annotationTypes.find(
            (at) =>
                at.name == "Segmentation OCT B-scan" &&
                at.interpretation == interpretation,
        );
        if (!annotationType) {
            throw new Error("Annotation type not found");
        }
        const item = { ...annotation, annotationType, creator };
        return data.annotations.create(item);
    }

    async function duplicateAnnotation(interpretation: string) {
        dialogue.set(`duplicating annotation ${annotation.id}...`);

        const newAnnotation = await getNewAnnotation(interpretation);
        const newSegmentationItem =
            segmentationController.getSegmentationItem(newAnnotation);

        const scanNr = viewerContext.index;
        newSegmentationItem.importOther(scanNr, segmentation);

        dialogue.set(undefined);
    }

    function duplicateMulticlass() {
        duplicateAnnotation("Label numbers");
    }

    function duplicateMultilabel() {
        duplicateAnnotation("Layer bits");
    }

    async function importFromOther() {
        const hide = () => dialogue.set(undefined);
        const reject = hide;
        const resolve = (
            other: MulticlassSegmentation | MultilabelSegmentation,
        ) => {
            const scanNr = viewerContext.index;
            segmentation.importOther(scanNr, other);
            segmentationItem.checkpoint(scanNr);
            hide();
        };

        const availableSegmentations =
            segmentationController.allSegmentations.filter(
                (s) =>
                    s != segmentation &&
                    (s instanceof MulticlassSegmentation ||
                        s instanceof MultilabelSegmentation),
            );
        const d = {
            query: ImportSegmentationSelector,
            props: {
                segmentation,
                availableSegmentations,
            },
            approve: "Import",
            decline: "Cancel",
            resolve,
            reject,
        };

        dialogue.set(d);
    }

    let selectedLabelNames: string[] = $state([]);

    function toggleShow() {
        segmentationContext.toggleShow(segmentation);
    }
    function toggleActive() {
        segmentationContext.toggleActive(segmentation);
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main" class:active>
    <label>
        Opacity:
        <input
            type="range"
            bind:value={layerSegmentationOverlay.alpha}
            min="0"
            max="1"
            step="0.01"
        />
    </label>
    {#if active && image.is3D && segmentation}
        {#if annotationType.name != "Segmentation OCT Volume"}
            <BscanLinks {annotation} {segmentation} />
        {/if}
    {/if}

    <div class="row">
        <div>
            {#if segmentationContext.hideSegmentations.has(segmentation)}
                <PanelIcon onclick={toggleShow} tooltip="Hide"
                    ><Hide /></PanelIcon
                >
            {:else}
                <PanelIcon onclick={toggleShow} tooltip="Show"
                    ><Show /></PanelIcon
                >
            {/if}
        </div>

        <div class="expand" onclick={toggleActive}>
            <div class="feature-name">{feature.name}</div>
            <div class="annotationID">{annotation.id}</div>
        </div>

        {#if isEditable}
            <PanelIcon onclick={removeAnnotation} tooltip="Delete">
                <Trash />
            </PanelIcon>
        {/if}
    </div>

    {#if active}
        {#if annotationType.name == "Segmentation OCT Volume"}
            <div class="row">
                <LayerThicknessSelector {image} {segmentation} />
            </div>
        {/if}
        <div class="row">
            <PanelIcon
                onclick={duplicateMulticlass}
                tooltip="Duplicate numbers"
            >
                <Duplicate />
            </PanelIcon>
            <PanelIcon onclick={duplicateMultilabel} tooltip="Duplicate bits">
                <Duplicate />
            </PanelIcon>

            {#if isEditable}
                <PanelIcon onclick={importFromOther} tooltip="Import B-scan">
                    <ImportSegmentation />
                </PanelIcon>
            {/if}
        </div>

        {#if isEditable}
            <div class="row">
                <div class="layer-select">
                    <div>Select layers to edit:</div>
                    <ul>
                        {#each Object.keys(macularLayers) as layer}
                            {#if layer != "background"}
                                <li>
                                    <label>
                                        {#if annotationType.interpretation == "Layer bits"}
                                            <input
                                                type="checkbox"
                                                value={layer}
                                                bind:group={selectedLabelNames}
                                            />
                                        {:else if annotationType.interpretation == "Label numbers"}
                                            <input
                                                type="radio"
                                                value={layer}
                                                bind:group={selectedLabelNames}
                                            />
                                        {/if}
                                        {layer}
                                    </label>
                                </li>
                            {/if}
                        {/each}
                    </ul>
                </div>
            </div>

            <div class="row">
                <SegmentationTools {segmentationItem} {selectedLabelNames} />
            </div>
        {/if}
    {/if}
</div>

<style>
    div {
        display: flex;
        align-items: center;
    }
    div.main {
        flex-direction: column;
        border-left: 2px solid rgba(255, 255, 255, 0);
        border-radius: 2px;
    }
    div.main.active {
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
        max-width: 12em;
        padding-right: 0.5em;
    }
    div.annotationID {
        font-size: x-small;
        align-items: end;
        flex: 0;
    }
    div.layer-select {
        display: flex;
        flex-direction: column;
    }
    ul {
        list-style-type: none;
        padding: 0;
    }
</style>
