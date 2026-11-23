<script lang="ts">
    import { fromHex, toHex } from "$lib/utils";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { getContext } from "svelte";
    import type { Segmentation } from "./segmentationContext.svelte";

    let { segmentation }: { segmentation: Segmentation } = $props();

    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");

    let currentColor = $state(
        toHex(mainViewerContext.getFeatureColor(segmentation)),
    );

    function handleColorChange(e: Event) {
        const newColor = (e.target as HTMLInputElement).value;
        mainViewerContext.setFeatureColor(segmentation, fromHex(newColor));
        currentColor = newColor;
    }
</script>

<!-- A 24 px target around a 12 px chip; the native colour input is the control, so it is a tab stop. -->
<label
    class="relative flex size-6 shrink-0 cursor-pointer items-center justify-center focus-within:outline-2 focus-within:-outline-offset-2 focus-within:outline-focus"
>
    <span
        class="size-3 rounded-full"
        style:background-color={currentColor}
        aria-hidden="true"
    ></span>
    <input
        type="color"
        aria-label="Color"
        class="absolute inset-0 size-full cursor-pointer opacity-0"
        value={currentColor}
        oninput={handleColorChange}
    />
</label>
