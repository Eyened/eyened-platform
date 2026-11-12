<!--
@component
"Area this slice" under a segmentation row. Nothing for class masks, whose areas are per class, or for an image without a resolution.
-->
<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
    import { BinaryMask, ProbabilityMask } from "$lib/webgl/mask.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import { getContext } from "svelte";

    let {
        segmentation,
        segmentationItem,
    }: { segmentation: Segmentation; segmentationItem: SegmentationItem } =
        $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { resolution } = viewerContext.image;
    let area = $state<number | undefined>(undefined);

    // getMask may create the slice's state, so this runs in an effect, not a derived.
    $effect(() => {
        area = undefined;
        if (!(resolution.x > 0 && resolution.y > 0)) return;
        const mask = segmentationItem.getMask(viewerContext.index);
        let pixels: number;
        if (mask instanceof ProbabilityMask) {
            void mask.pixelArea; // reruns when the data changes; the threshold applies at read time
            pixels = mask.computePixelArea(
                segmentationItem.threshold ?? segmentation.threshold ?? 0.5,
            );
        } else if (mask instanceof BinaryMask) {
            pixels = mask.pixelArea;
        } else {
            return;
        }
        area = (pixels * resolution.x * resolution.y) / 1e6;
    });
</script>

{#if area !== undefined}
    <p class="text-helper-text-01 text-text-secondary">
        Area this slice: {area < 0.01
            ? `${(area * 1e6).toFixed(0)} μm²`
            : `${area.toFixed(4)} mm²`}
    </p>
{/if}
