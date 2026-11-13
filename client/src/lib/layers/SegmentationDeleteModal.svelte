<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { deleteSegmentation, segmentations } from "$lib/data";
    import type {
        Segmentation,
        SegmentationContext,
    } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";

    // Carbon danger modal. It lives in the section, because a delete unmounts the row.
    let {
        segmentation,
        segmentationContext,
        open = $bindable(false),
        onfallback,
    }: {
        segmentation: Segmentation | null;
        segmentationContext: SegmentationContext;
        open?: boolean;
        /** Moves focus somewhere that still exists after the row is gone. */
        onfallback: () => void;
    } = $props();

    async function remove(target: Segmentation) {
        // Model segmentations live in another table; never send their id to this API.
        if (target.annotation_type === "grader_segmentation") {
            await deleteSegmentation(target.id);
        }
        if (segmentationContext.isActiveSegmentation(target)) {
            segmentationContext.segmentationItem = undefined;
            segmentationContext.activeIndices = [];
        }
    }

    function focusFallbackIfDeleted(event: Event) {
        if (segmentation && !segmentations.has(segmentation.id)) {
            event.preventDefault();
            onfallback();
        }
    }
</script>

<Modal
    bind:open
    danger
    size="xs"
    modalHeading="Delete segmentation"
    modalLabel={segmentation
        ? `${segmentation.feature.name} [${segmentation.id}]`
        : undefined}
    primaryButtonText="Delete"
    primaryButtonLoadingDescription="Deleting…"
    successDescription="Deleted"
    errorTitle="Segmentation could not be deleted"
    onsubmit={() => (segmentation ? remove(segmentation) : false)}
    onCloseAutoFocus={focusFallbackIfDeleted}
>
    <p>
        Deletes the segmentation and everything drawn in it. This can't be
        undone.
    </p>
</Modal>
