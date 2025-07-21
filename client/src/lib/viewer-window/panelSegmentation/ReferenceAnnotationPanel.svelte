<script lang="ts">
    
    import { dialogueManager } from "$lib/dialogue/DialogueManager";
    import { AbstractImage } from "$lib/webgl/abstractImage";
    import { Intersection, PanelIcon, Hide, Show, Trash } from "../icons/icons";
    import ReferenceAnnotationSelector from "./ReferenceAnnotationSelector.svelte";
    import { getContext } from "svelte";
    import type { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem";
    import type { Segmentation } from "$lib/datamodel/segmentation.svelte";
    interface Props {
        segmentationItem: SegmentationItem;
        segmentation: Segmentation;
        image: AbstractImage;
        isEditable: boolean;
    }
    let { segmentation, image, isEditable, segmentationItem }: Props = $props();

    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );

    function setAnnotationReference() {
        dialogueManager.show(
            ReferenceAnnotationSelector,
            {
                segmentation,
                image,
            },
            (other: Segmentation) => {
                segmentation.update({
                    referenceSegmentationId: other.id,
                });
            },
        );
    }

    function removeReference() {
        segmentation.update({ referenceSegmentationId: null });
    }
    function toggleApplyMask() {
        segmentationOverlay.toggleMasking(segmentationItem);
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main">
    <h3><Intersection size="1.5em" />Reference mask</h3>
    {#if isEditable}
        <div
            class="row"
            class:editable={isEditable}
            onclick={() => isEditable && setAnnotationReference()}
        >
            <span> Update reference mask</span>
        </div>
    {/if}
    {#if segmentation.referenceId}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="row">
            Mask ID: [{segmentation.referenceId}]
            {#if isEditable}
                <PanelIcon
                    onclick={removeReference}
                    tooltip="Remove reference mask"
                    Icon={Trash}
                />
            {/if}
        </div>

        <div class="row editable" onclick={toggleApplyMask}>
            {#if segmentationOverlay.applyMasking.has(segmentationItem)}
                <Hide size="1.5em" />
                <span>Showing masked annotation</span>
            {:else}
                <Show size="1.5em" />
                <span>Showing unmasked annotation</span>
            {/if}
        </div>
    {/if}
</div>

<style>
    div {
        display: flex;
    }
    h3 {
        margin: 0;
        margin-bottom: 0.2em;
        display: flex;
        align-items: center;
        gap: 0.5em;
        font-size: small;
    }
    div.row {
        flex-direction: row;
        align-items: center;
        gap: 0.5em;
        font-size: x-small;
        padding: 0.4em;
    }
    div.row.editable {
        cursor: pointer;
    }
    div.row.editable:hover {
        background-color: rgba(100, 255, 255, 0.3);
    }
    div.main {
        flex-direction: column;
        background-color: rgba(255, 255, 255, 0.1);
        flex: 1;
        padding: 0.2em;
    }

    span:hover {
        opacity: 1;
    }
</style>
