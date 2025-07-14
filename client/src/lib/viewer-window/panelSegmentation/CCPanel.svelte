<script lang="ts">
    import { ConnectedComponents, PanelIcon } from "../icons/icons";
    import { getContext } from "svelte";
    import type { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem";

    interface Props {
        segmentationItem: SegmentationItem;
    }
    let { segmentationItem }: Props = $props();

    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );

    let connectedComponentsActive = $derived(
        segmentationOverlay.applyConnectedComponents.has(segmentationItem),
    );
    function toggleConnectedComponents() {
        segmentationOverlay.toggleConnectedComponents(segmentationItem);
    }
</script>
<div class="main">
    <h3><ConnectedComponents size="1.5em" />Connected components</h3>
    <label>
        <input type="checkbox" bind:checked={connectedComponentsActive} />
        Show connected components
    </label>
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
