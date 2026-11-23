<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import RenderModeSelect from "./RenderModeSelect.svelte";
    import Stretch from "./Stretch.svelte";
    import WindowLevel from "./WindowLevel.svelte";

    let { radio = true } = $props();
    const viewerContext = getContext<ViewerContext>("viewerContext");
</script>

<div class="main">
    <div class="section">
        <WindowLevel />
    </div>

    <div>
        <RenderModeSelect
            bind:value={viewerContext.renderMode}
            supportsColor={viewerContext.image.supportsColorRenderModes}
            {radio}
        />
    </div>

    {#if viewerContext.image.orientation === "axial"}
        <div class="section">
            <Stretch />
        </div>
    {/if}
</div>

<style>
    div {
        display: flex;
    }
    div.main {
        padding: 0.5em;
        flex-direction: column;
    }
    div.section {
        margin-top: 1em;
        padding-top: 1em;
        border-top: 1px solid rgba(255, 255, 255, 0.2);
    }
</style>
