<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import {
        getAvailableRenderModes,
        type RenderMode,
    } from "$lib/viewer/viewer-utils";
    import { getContext } from "svelte";
    import WindowLevel from "./WindowLevel.svelte";
    import Stretch from "./Stretch.svelte";

    let { radio = true } = $props();
    const viewerContext = getContext<ViewerContext>("viewerContext");

    const labels: Record<RenderMode, string> = {
        Original: "O<u>r</u>iginal",
        "Contrast enhanced": "Contrast <u>e</u>nhanced",
        "Color balanced": "Color <u>b</u>alanced",
        CLAHE: "CLA<u>H</u>E",
        Sharpened: "<u>S</u>harpened",
        "Histogram matched": "Histogram <u>m</u>atched",
        Luminance: "<u>L</u>uminance",
        Red: "Red",
        Green: "Green",
        Blue: "Blue",
    };

    const availableModes = $derived(
        getAvailableRenderModes(viewerContext.image.supportsColorRenderModes),
    );

    // Drop modes that are not available for this image (e.g. after switching)
    $effect(() => {
        if (!availableModes.includes(viewerContext.renderMode)) {
            viewerContext.renderMode = "Original";
        }
    });
</script>

<div class="main">
    <div class="section">
        <WindowLevel />
    </div>

    <div>
        {#if radio}
            <ul>
                {#each availableModes as option}
                    <li>
                        <label>
                            <input
                                type="radio"
                                bind:group={viewerContext.renderMode}
                                value={option}
                            />
                            <!-- eslint-disable-next-line svelte/no-at-html-tags -- trusted, non-user content -->
                            {@html labels[option]}
                        </label>
                    </li>
                {/each}
            </ul>
        {:else}
            <select bind:value={viewerContext.renderMode}>
                {#each availableModes as option}
                    <option value={option}>
                        {option}
                    </option>
                {/each}
            </select>
        {/if}
    </div>

    {#if viewerContext.image.orientation === "axial"}
        <div class="section">
            <Stretch />
        </div>
    {/if}
</div>

<style>
    label {
        white-space: nowrap;
    }
    div {
        display: flex;
    }
    div.main {
        padding: 0.5em;
    }
    div.main {
        flex-direction: column;
    }
    div.section {
        margin-top: 1em;
        padding-top: 1em;
        border-top: 1px solid rgba(255, 255, 255, 0.2);
    }

    ul {
        list-style-type: none;
        padding: 0;
    }
    label:hover {
        color: white;
    }
</style>
