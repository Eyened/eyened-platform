<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import SegmentationPickerModal from "$lib/layers/SegmentationPickerModal.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { converters } from "$lib/webgl/segmentationConverter";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import { getContext } from "svelte";
    import type { Segmentation } from "./segmentationContext.svelte";
    import { orderSegmentationsByCreator } from "./segmentationUtils";

    interface Props {
        segmentation: Segmentation;
        image: AbstractImage;
        segmentationItem: SegmentationItem;
    }
    let { segmentation, image, segmentationItem }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const { segmentationContext } =
        getContext<MainViewerContext>("mainViewerContext");
    let open = $state(false);

    // AI first, then the grader's own, then colleagues'; only rows whose data converts into this one, never the row itself.
    const rows = $derived(
        orderSegmentationsByCreator(
            segmentationContext.modelSegmentations,
            segmentationContext.graderSegmentations,
            globalContext.user.id,
        ).filter(
            (s) =>
                !(
                    s.id === segmentation.id &&
                    s.annotation_type === segmentation.annotation_type
                ) &&
                (s.data_representation === segmentation.data_representation ||
                    `${segmentation.data_representation}->${s.data_representation}` in
                        converters),
        ),
    );

    // Replaces this slice's mask; undo reverses it. The picked segmentation's slice is loaded first if it isn't yet.
    async function importFrom(other: Segmentation) {
        const index = viewerContext.index;
        const item = image.getOrCreateSegmentationItem(other);
        await item.ready;
        const state = item.getSegmentationState(index, true)!;
        await state.loaded;
        if (state.isEmptyForSlice)
            throw new Error("It has nothing on this slice.");
        await segmentationItem.importOther(index, state.mask);
    }
</script>

<Button variant="ghost" size="sm" onclick={() => (open = true)}
    >{image.is3D ? "Import into this B-scan…" : "Import…"}</Button
>
<SegmentationPickerModal
    bind:open
    modalHeading={image.is3D
        ? "Import into this B-scan"
        : "Import into this image"}
    modalLabel="{segmentation.feature.name} [{segmentation.id}]"
    primaryButtonText="Import"
    primaryButtonLoadingDescription="Importing…"
    successDescription="Imported"
    errorTitle="Segmentation could not be imported"
    {rows}
    emptyTitle="Nothing to import"
    emptyDescription="No other segmentation of this image can be imported into this one."
    onpick={importFrom}
/>
