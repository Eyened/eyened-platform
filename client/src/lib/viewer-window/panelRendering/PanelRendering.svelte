<script lang="ts">
    import {
        ANGIO_DISPLAY_LABELS,
        ANGIO_DISPLAY_MODES,
    } from "$lib/viewer/angioDisplayMode";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { ViewerWindowContext } from "$lib/viewer-window/viewerWindowContext.svelte";
    import { getContext } from "svelte";
    import RenderModeSelect from "./RenderModeSelect.svelte";
    import Stretch from "./Stretch.svelte";
    import WindowLevel from "./WindowLevel.svelte";

    let { radio = true } = $props();
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    // octaFlowReady bumps when flow attaches after structural was already shown
    let hasAngioFlow = $derived(
        viewerContext.image.hasFlow ||
            viewerWindowContext.octaFlowReady.get(
                viewerContext.image.instance?.id ?? "",
            ) === true,
    );
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

    {#if hasAngioFlow}
        <div class="section">
            <ul role="radiogroup" aria-label="Angio display">
                {#each ANGIO_DISPLAY_MODES as mode (mode)}
                    <li>
                        <label>
                            <input
                                type="radio"
                                bind:group={viewerContext.angioDisplayMode}
                                value={mode}
                            />
                            {ANGIO_DISPLAY_LABELS[mode]}
                        </label>
                    </li>
                {/each}
            </ul>
        </div>
    {/if}

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
    ul {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 0.25em;
    }
    label {
        display: flex;
        align-items: center;
        gap: 0.5em;
        cursor: pointer;
    }
</style>
