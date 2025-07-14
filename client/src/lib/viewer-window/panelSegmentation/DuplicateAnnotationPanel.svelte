<script lang="ts">
    import { Annotation } from "$lib/datamodel/annotation.svelte";
    import { AbstractImage } from "$lib/webgl/abstractImage";
    import { Duplicate, PanelIcon } from "../icons/icons";
    import { dialogueManager } from "$lib/dialogue/DialogueManager";
    import { AnnotationType } from "$lib/datamodel/annotationType.svelte";
    import { getContext } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import {
        ProbabilitySegmentation,
        type Segmentation,
    } from "$lib/webgl/segmentation";
    import { data } from "$lib/datamodel/model";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { SegmentationItem } from "$lib/webgl/segmentationItem";
    import Toggle from "$lib/Toggle.svelte";
    import { getAnnotationTypes } from "./annotationTypes";
    interface Props {
        annotation: Annotation;
        image: AbstractImage;
        segmentationItem: SegmentationItem;
        segmentation: Segmentation;
    }

    let { annotation, image, segmentationItem, segmentation }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { creator } = getContext<GlobalContext>("globalContext");

    let duplicateVolume = $state(false);
    let type = $state<"Q" | "B" | "P">("Q");
    if (annotation.annotationType.dataRepresentation == "DualBitMask") {
        type = "Q";
    } else if (annotation.annotationType.dataRepresentation == "Binary") {
        type = "B";
    } else if (annotation.annotationType.dataRepresentation == "Probability") {
        type = "P";
    }
    const types = getAnnotationTypes();

    async function duplicate() {
        dialogueManager.showQuery(`Duplicating annotation ${annotation.id}...`);

        let annotationType: AnnotationType;
        if (annotation.annotationType.dataRepresentation == "MultiClass" || annotation.annotationType.dataRepresentation == "MultiLabel") {
            // same as original annotation type
            annotationType = annotation.annotationType;
        } else {
            // new annotation can be of different type
            annotationType = types[type];
        }

        const item = {
            ...annotation,
            annotationTypeId: annotationType.id,
            // annotationReferenceId needs to be mentioned explicitly, because it's marked with $state and hence not enumerable
            annotationReferenceId: annotation.annotationReferenceId,
            // overwrite creatorId to current user
            creatorId: creator.id,
        };

        const newAnnotation = await Annotation.create(item);

        const newSegmentationItem = image.getSegmentationItem(newAnnotation);
        if (duplicateVolume) {
            for (let scanNr = 0; scanNr < image.depth; scanNr++) {
                const segmentation = segmentationItem.getSegmentation(scanNr);
                if (segmentation) {
                    await newSegmentationItem.importOther(scanNr, segmentation);
                }
            }
        } else {
            const scanNr = viewerContext.index;
            await newSegmentationItem.importOther(scanNr, segmentation);
        }

        dialogueManager.hide();
    }
</script>

<div class="main">
    <h3><Duplicate size="1.5em" />Duplicate</h3>

    {#if image.is3D}
        <div>
            <label>
                <input type="radio" bind:group={duplicateVolume} value={true} />
                Volume
            </label>
            <label>
                <input
                    type="radio"
                    bind:group={duplicateVolume}
                    value={false}
                />
                B-scan
            </label>
        </div>
    {/if}
    {#if annotation.annotationType.dataRepresentation == "MultiClass" || annotation.annotationType.dataRepresentation == "MultiLabel"}{:else}
        <div>
            <label>
                <input type="radio" bind:group={type} value="Q" />
                Q
            </label>
            <label>
                <input type="radio" bind:group={type} value="B" />
                B
            </label>
            <label>
                <input type="radio" bind:group={type} value="P" />
                P
            </label>
        </div>
    {/if}
    <button onclick={duplicate}>Create copy</button>
</div>

<style>
    div.main {
        flex-direction: column;
        background-color: rgba(255, 255, 255, 0.1);
        flex: 1;
        padding: 0.2em;
        margin-bottom: 0.2em;
        margin-top: 0.2em;
    }
    h3 {
        font-size: small;
        font-weight: bold;
        margin: 0;
        padding: 0;
        display: flex;
        align-items: center;
        gap: 0.5em;
    }
</style>
