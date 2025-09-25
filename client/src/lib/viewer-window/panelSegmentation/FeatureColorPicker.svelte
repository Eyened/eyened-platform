<script lang="ts">
    import { fromHex, toHex } from "$lib/utils";
    import type { MainViewerContext } from "$lib/viewer/overlays/SegmentationOverlay.svelte";

    import { getContext } from "svelte";
    import type { SegmentationGET } from "../../../types/openapi_types";
    import PanelIcon from "../icons/PanelIcon.svelte";

    interface Props {
        segmentation: SegmentationGET;
    }   
    let { segmentation }: Props = $props();

    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );

    let currentColor = $state("");

    currentColor = toHex(mainViewerContext.getFeatureColor(segmentation));
    function handleColorChange(e: Event) {
        const newColor = (e.target as HTMLInputElement).value;
        mainViewerContext.setFeatureColor(segmentation, fromHex(newColor));
        currentColor = newColor;
    }
</script>

<PanelIcon tooltip="Change color">
    <label class="tool">
        <i class="color-picker" style="background-color: {currentColor};"></i>
        <input type="color" value={currentColor} oninput={handleColorChange} />
    </label>
</PanelIcon>

<style>
    input {
        visibility: hidden;
        position: absolute;
    }
    i.color-picker {
        cursor: pointer;
        width: 1.2em;
        height: 1.2em;
        margin: 0.1em;
        border-radius: 50%;
        display: flex;
    }
</style>
