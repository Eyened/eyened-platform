<script lang="ts">
    import { colors } from "$lib/viewer/overlays/colors";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import { Hide, PanelIcon, Show } from "../icons/icons";
    import { type Segmentation } from "./segmentationContext.svelte";

    interface Props {
        segmentation: Segmentation;
        active: boolean;
    }
    let { segmentation, active }: Props = $props();

    const { feature, data_representation } = segmentation;

    const groupType = {
        MultiLabel: "checkbox",
        MultiClass: "radio",
    }[data_representation as "MultiLabel" | "MultiClass"];

    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");

    const { segmentationContext } = mainViewerContext;

    let activeIndices = $state<number | number[]>(0);

    function indicesEqual(a: number | number[], b: number | number[]): boolean {
        if (Array.isArray(a) && Array.isArray(b)) {
            return a.length === b.length && a.every((v, i) => v === b[i]);
        }
        if (!Array.isArray(a) && !Array.isArray(b)) {
            return a === b;
        }
        if (!Array.isArray(a) && Array.isArray(b) && b.length === 1) {
            return a === b[0];
        }
        if (Array.isArray(a) && a.length === 1 && !Array.isArray(b)) {
            return a[0] === b;
        }
        return false;
    }

    $effect(() => {
        if (active) {
            segmentationContext.activeIndices = activeIndices;
        }
    });

    $effect(() => {
        if (!active) return;
        const fromCtx = segmentationContext.activeIndices;
        if (!indicesEqual(activeIndices, fromCtx)) {
            activeIndices = fromCtx;
        }
    });

    function pointerEnter(featureIndex: number) {
        mainViewerContext.highlightedFeatureIndex = featureIndex;
    }
    function pointerLeave() {
        mainViewerContext.highlightedFeatureIndex = undefined;
    }

    function toggleLayerVisibility(featureIndex: number, e: MouseEvent) {
        e.preventDefault();
        e.stopPropagation();
        segmentationContext.toggleFeatureLayerVisibility(
            segmentation,
            featureIndex,
        );
        viewerContext.repaint();
    }
</script>

<div class:hidden={!active}>
    {#if data_representation === "MultiClass"}
        <div class="mc-opacity" role="group" aria-label="Class overlay opacity">
            <label class="mc-op" title="Active class opacity">
                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    bind:value={segmentationContext.multiClassActiveAlpha}
                />
            </label>
            <label class="mc-op" title="Other classes opacity">
                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    bind:value={segmentationContext.multiClassInactiveAlpha}
                />
            </label>
        </div>
    {/if}
    <ul>
        {#each feature.subfeatures as subfeature (subfeature.index)}
            <li
                onpointerenter={() => pointerEnter(subfeature.index)}
                onpointerleave={pointerLeave}
            >
                <div class="feature-container">
                    <div class="layer-visibility">
                        <PanelIcon
                            tooltip={segmentationContext.isFeatureLayerVisible(
                                segmentation,
                                subfeature.index,
                            )
                                ? "Hide layer"
                                : "Show layer"}
                            onclick={(e) =>
                                toggleLayerVisibility(subfeature.index, e)}
                            Icon={segmentationContext.isFeatureLayerVisible(
                                segmentation,
                                subfeature.index,
                            )
                                ? Show
                                : Hide}
                            size={1.2}
                        />
                    </div>
                    <div
                        class="color-box"
                        style="background-color: rgb({colors[
                            subfeature.index - 1
                        ]});"
                    >
                        <span class="feature-index">{subfeature.index}</span>

                        <label>
                            {#if groupType == "radio"}
                                <input
                                    type="radio"
                                    bind:group={activeIndices}
                                    value={subfeature.index}
                                />
                            {:else}
                                <input
                                    type="checkbox"
                                    bind:group={activeIndices}
                                    value={subfeature.index}
                                />
                            {/if}
                            <span class="feature-name">{subfeature.name}</span>
                        </label>
                    </div>
                </div>
            </li>
        {/each}
    </ul>
</div>

<style>
    ul {
        list-style-type: none;
        padding: 0;
    }
    li {
        display: flex;
        align-items: center;
        gap: 0.5em;
    }
    li:hover {
        background-color: rgba(100, 255, 255, 0.3);
    }
    div.feature-container {
        display: flex;
        align-items: center;
        gap: 0.35em;
        flex: 1;
        min-width: 0;
    }
    .layer-visibility {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
    }
    .layer-visibility :global(svg) {
        width: 1em;
        height: 1em;
        display: block;
    }
    div.color-box {
        display: flex;
        align-items: left;
        /* width: 1.5em; */
        /* height: 1.5em; */
        flex-grow: 1;
        font-size: x-small;
        padding-top: 0.1em;
        padding-bottom: 0.1em;
        border-top-left-radius: 0.25em;
        border-bottom-left-radius: 0.25em;
        /* text-align: center; */
        align-items: left;
        /* justify-content: center;
		flex-shrink: 0; */
    }
    label {
        display: flex;
        flex: 1;
        align-items: center;
        gap: 0.35em;
    }
    span.feature-index {
        flex: 0 0 auto;
        text-align: right;
        min-width: 2em;
    }
    span.feature-name {
        flex: 1;
        text-align: left;
        background-color: rgba(0, 0, 0, 0.5);
    }
    div.hidden {
        display: none;
    }
    .mc-opacity {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.35em;
        padding: 0.15em 0.25em 0.35em;
        font-size: 0.65rem;
        line-height: 1;
        border-bottom: 1px solid rgba(100, 255, 255, 0.15);
    }
    .mc-op {
        display: flex;
        flex: 1;
        align-items: center;
        gap: 0.25em;
        min-width: 0;
        margin: 0;
        cursor: default;
    }
    .mc-op .k {
        flex: 0 0 auto;
        opacity: 0.8;
        font-weight: 600;
        width: 1.6em;
    }
    .mc-op input[type="range"] {
        flex: 1;
        min-width: 0;
        height: 0.85em;
        margin: 0;
        padding: 0;
        accent-color: rgb(100, 255, 255);
    }
</style>
