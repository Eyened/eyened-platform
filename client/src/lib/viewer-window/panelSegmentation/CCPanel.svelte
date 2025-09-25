<script lang="ts">
    import type { MainViewerContext } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem";
    import { getContext } from "svelte";
    import { ConnectedComponents } from "../icons/icons";

    interface Props {
        segmentationItem: SegmentationItem;
    }
    let { segmentationItem }: Props = $props();

    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );

    let connectedComponentsActive = $derived(
        mainViewerContext.applyConnectedComponents.has(segmentationItem),
    );
    function toggleConnectedComponents() {
        mainViewerContext.toggleConnectedComponents(segmentationItem);
    }
</script>
<div class="main">
    <h3><ConnectedComponents size="1.5em" />Connected components</h3>
    <label>
        <input type="checkbox" checked={connectedComponentsActive} onchange={toggleConnectedComponents} />
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
