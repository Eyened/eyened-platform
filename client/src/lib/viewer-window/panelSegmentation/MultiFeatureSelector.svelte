<script lang="ts">
    import { colors } from "$lib/viewer/overlays/colors";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { getContext } from "svelte";
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

    const mainViewerContext = getContext<MainViewerContext>(
        "mainViewerContext",
    );

    const { segmentationContext } = mainViewerContext;
    function pointerEnter(featureIndex: number) {
        mainViewerContext.highlightedFeatureIndex = featureIndex;
    }
    function pointerLeave() {
        mainViewerContext.highlightedFeatureIndex = undefined;
    }

    let activeIndices = $state(0);
    $effect(() => {
        if (active) {
            segmentationContext.activeIndices = activeIndices;
        }
    });
</script>

<div class:hidden={!active}>
    <ul>
        {#each feature.subfeatures as subfeature}
            <li
                onpointerenter={() => pointerEnter(subfeature.index)}
                onpointerleave={pointerLeave}
            >
                <div class="feature-container">
                    <div
                        class="color-box"
                        style="background-color: rgb({colors[
                            subfeature.index - 1
                        ]});"
                    >
                        {subfeature.index}
                    </div>

                    <label>
                        {#if groupType == "radio"}
                            <input
                                type="radio"
                                bind:group={activeIndices}
                                value={subfeature.index}
                            />
                            {subfeature.name}
                        {:else}
                            <input
                                type="checkbox"
                                bind:group={activeIndices}
                                value={subfeature.index}
                            />
                            {subfeature.name}
                        {/if}
                    </label>
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
    }
    div.color-box {
        display: inline-block;
        width: 1.5em;
        height: 1.5em;
        border-radius: 0.75em;
        border: 1px solid rgba(0, 0, 0, 0.1);
        text-align: center;
        justify-content: center;
    }
    label {
        display: flex;
        flex: 1;
    }
    div.hidden {
        display: none;
    }
</style>
